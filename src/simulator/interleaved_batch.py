"""
Interleaved Batch Simulator
============================

Subclass of BatchTaskSimulator that supports phase-level task
interleaving within a shared conversation window.

Architecture::

  Original (serial):
    Batch → [Task1 all turns] → [Task2 all turns] → [Task3 all turns]

  Interleaved:
    Batch (shared window)
      ├── T1.observation  (turns 1-5)
      ├── T2.observation  (turns 6-10)
      ├── T3.observation  (turns 11-13)
      ├── T1.probing      (turns 14-17)   ← T1 info now far away
      ├── T2.probing      (turns 18-20)
      └── ...

New classes (all independent, no existing code modified):
  - SharedConversationWindow — manages the shared dialogue history
  - InterleavedScheduler — decides which (task, phase) to run next
  - InterleavedBatchSimulator(BatchTaskSimulator) — orchestrates it all

Safety:
  - BatchTaskSimulator is NOT modified
  - interleave_mode=False → super().run_batch() (original serial behavior)
  - Can be swapped back to BatchTaskSimulator at any time
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import re

from .batch_task_simulator import BatchTaskSimulator, BatchConfig, BatchResult
from .evaluator import Evaluator
from .image_policy import ImageInjectionPolicy
from .llm_client import LLMClient
from .stateful_simulator import StatefulStrategicSimulator
from .state_aware_evaluator import StateAwareEvaluator
from .task_progress import TaskProgress
from .action_space import TASK_STRATEGIES

logger = logging.getLogger(__name__)


# ============================================================
# SharedConversationWindow
# ============================================================

class SharedConversationWindow:
    """
    Shared dialogue history for all tasks within a batch.

    All tasks' turns are appended to the same window so the target
    model sees a single continuous conversation. Each turn is tagged
    with its task_id for the core model / evaluator to use.
    """

    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.full_history: List[Dict[str, Any]] = []
        self.current_turn: int = 0
        self.task_contexts: Dict[str, Dict[str, Any]] = {}
        # task_id -> metadata (task_type, current_phase, etc.)

    def add_turn(self, task_id: str, turn_data: Dict[str, Any]):
        """Append a turn to the shared history."""
        turn_data["_task_id"] = task_id
        turn_data["_global_turn"] = self.current_turn
        self.full_history.append(turn_data)
        self.current_turn += 1

    def register_task(self, task_id: str, metadata: Dict[str, Any]):
        """Register a task's metadata in the shared window."""
        self.task_contexts[task_id] = metadata

    @property
    def is_exhausted(self) -> bool:
        return self.current_turn >= self.max_turns

    # --- History views ---

    def get_history_for_target_model(
        self,
        compress_early: bool = True,
        keep_recent: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get the full conversation history for the target model.

        All tasks' turns are included (the target model sees one
        continuous conversation). Early turns can be compressed.
        """
        if not compress_early or len(self.full_history) <= keep_recent:
            return list(self.full_history)

        # Compress early history into a summary turn
        early = self.full_history[:-keep_recent]
        recent = self.full_history[-keep_recent:]

        summary_parts = []
        for h in early:
            msg = str(h.get("user_message", h.get("message", "")))[:60]
            resp = str(h.get("model_response", h.get("response", "")))[:60]
            summary_parts.append(f"[{h.get('_task_id', '?')}] Q: {msg}... A: {resp}...")

        summary_turn = {
            "role": "system",
            "content": "[Earlier conversation summary]\n" + "\n".join(summary_parts),
            "_is_summary": True,
        }
        return [summary_turn] + recent

    def get_history_for_core_model(self, current_task_id: str) -> str:
        """
        Get a focused summary for the core (examiner) model.

        Emphasizes the current task's turns; compresses other tasks.
        """
        focused = [h for h in self.full_history if h.get("_task_id") == current_task_id]
        other = [h for h in self.full_history if h.get("_task_id") != current_task_id]

        lines = []
        if other:
            lines.append(f"[Other tasks: {len(other)} turns total]")
        for h in focused[-5:]:
            action = h.get("action", "?")
            msg = str(h.get("user_message", h.get("message", "")))[:100]
            resp = str(h.get("model_response", h.get("response", "")))[:100]
            lines.append(f"[Turn {h.get('_global_turn', '?')}] ({action}) {msg}")
            lines.append(f"  → {resp}")

        return "\n".join(lines) if lines else "(no history)"


# ============================================================
# InterleavedScheduler
# ============================================================

class InterleavedScheduler:
    """
    Phase-level interleaved scheduler.

    Decides the order in which (task_id, phase) segments are executed.
    Supports two strategies:
      - "round_robin": cycle through tasks, advancing one phase at a time
      - "interleaved": all tasks do observation first, then probing, etc.
    """

    def __init__(
        self,
        tasks: List[Dict[str, Any]],
        strategy: str = "round_robin",
    ):
        self.tasks = tasks
        self.strategy = strategy

        # Initialize progress trackers
        self.task_progress: Dict[str, TaskProgress] = {}
        for task in tasks:
            task_id = task.get("task_id", str(id(task)))
            task_type = task.get("task_type", "attribute_comparison")
            strat = TASK_STRATEGIES.get(task_type)
            phase_configs = strat.phases if strat else []

            self.task_progress[task_id] = TaskProgress(
                task_id=task_id,
                task_type=task_type,
                phases=[],
                current_phase_index=0,
                overall_status="not_started",
            )
            # Populate phases from strategy
            from .task_progress import PhaseCompletion
            for pc in phase_configs:
                self.task_progress[task_id].phases.append(
                    PhaseCompletion(
                        phase_name=pc.get("name", "unknown"),
                        min_turns=pc.get("min_turns", 2),
                    )
                )

        # Scheduling state
        self._queue: List[Tuple[str, str]] = []
        self._build_queue()

    def _build_queue(self):
        """Build the execution queue based on strategy."""
        if self.strategy == "interleaved":
            self._build_interleaved_queue()
        else:
            self._build_round_robin_queue()

    def _build_round_robin_queue(self):
        """
        Round-robin: T1.phase0 → T2.phase0 → T3.phase0 →
                     T1.phase1 → T2.phase1 → ...
        """
        # Find max number of phases across all tasks
        max_phases = max(
            (len(tp.phases) for tp in self.task_progress.values()),
            default=0,
        )
        for phase_idx in range(max_phases):
            for task_id, tp in self.task_progress.items():
                if phase_idx < len(tp.phases):
                    self._queue.append((task_id, tp.phases[phase_idx].phase_name))

    def _build_interleaved_queue(self):
        """
        Interleaved: same as round_robin but with a deliberate gap
        between observation and probing for the same task.

        T1.obs → T2.obs → T3.obs → T1.probe → T3.probe → T2.probe → ...
        """
        # Group phases by "phase type" (observation-like, probe-like, final-like)
        observation_phases = ("grounding", "entity_grounding", "target_presentation",
                              "image_observation", "chain_navigation")
        probe_phases = ("noise_injection", "stress_test", "memory_attack",
                        "relationship_probing", "chain_verification",
                        "noise_during_reasoning", "option_presentation",
                        "distractor_injection")
        final_phases = ("final_evaluation", "final_test", "final_answer",
                        "final_selection")

        # Collect segments by category
        obs_segments = []
        probe_segments = []
        final_segments = []
        other_segments = []

        for task_id, tp in self.task_progress.items():
            for phase in tp.phases:
                segment = (task_id, phase.phase_name)
                if phase.phase_name in observation_phases:
                    obs_segments.append(segment)
                elif phase.phase_name in probe_phases:
                    probe_segments.append(segment)
                elif phase.phase_name in final_phases:
                    final_segments.append(segment)
                else:
                    other_segments.append(segment)

        self._queue = obs_segments + probe_segments + other_segments + final_segments

    def next_segment(self) -> Optional[Tuple[str, str]]:
        """
        Return the next (task_id, phase_name) to execute,
        or None if all segments are done.
        """
        if not self._queue:
            return None
        return self._queue.pop(0)

    def report_phase_done(self, task_id: str, phase_name: str):
        """Report that a phase has been completed."""
        tp = self.task_progress.get(task_id)
        if tp:
            current = tp.current_phase
            if current and current.phase_name == phase_name:
                current.complete()
                tp.advance_to_next_phase()

    @property
    def all_done(self) -> bool:
        return len(self._queue) == 0


# ============================================================
# InterleavedBatchSimulator
# ============================================================

class InterleavedBatchSimulator(BatchTaskSimulator):
    """
    BatchTaskSimulator subclass with phase-level task interleaving.

    Extension points:
      1. __init__: add interleave_mode flag
      2. run_batch(): override to support interleaved scheduling

    Safety:
      - Original BatchTaskSimulator code is NOT modified
      - interleave_mode=False → super().run_batch() (exact original behavior)
      - interleave_mode=True  → new interleaved execution path

    Usage::

        # Interleaved mode
        sim = InterleavedBatchSimulator(llm_client, evaluator, interleave_mode=True)
        result = sim.run_batch(tasks)

        # Serial mode (identical to BatchTaskSimulator)
        sim = InterleavedBatchSimulator(llm_client, evaluator, interleave_mode=False)
        result = sim.run_batch(tasks)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        evaluator: Evaluator,
        config: Optional[BatchConfig] = None,
        verbose: bool = True,
        interleave_mode: bool = True,
        interleave_strategy: str = "round_robin",
    ):
        super().__init__(
            llm_client=llm_client,
            evaluator=evaluator,
            config=config,
            verbose=verbose,
        )
        self.interleave_mode = interleave_mode
        self.interleave_strategy = interleave_strategy

        # These are created per run_batch call
        self.shared_window: Optional[SharedConversationWindow] = None
        self.scheduler: Optional[InterleavedScheduler] = None

    # ------------------------------------------------------------------
    # Override: run_batch
    # ------------------------------------------------------------------

    def run_batch(self, tasks: List[Dict[str, Any]]) -> BatchResult:
        """
        Override: supports both serial and interleaved modes.

        interleave_mode=False → super().run_batch(tasks)
        interleave_mode=True  → _run_interleaved_batch(tasks)
        """
        if not self.interleave_mode:
            return super().run_batch(tasks)

        return self._run_interleaved_batch(tasks)

    # ------------------------------------------------------------------
    # New: interleaved batch execution
    # ------------------------------------------------------------------

    def _run_interleaved_batch(
        self, tasks: List[Dict[str, Any]]
    ) -> BatchResult:
        """Execute tasks with phase-level interleaving."""
        self._reset_session()

        result = BatchResult(
            batch_id=f"interleaved_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_time=datetime.now(),
            tasks_attempted=len(tasks),
        )

        # Initialize shared window and scheduler
        self.shared_window = SharedConversationWindow(
            max_turns=self.config.max_turns_per_session
        )
        self.scheduler = InterleavedScheduler(
            tasks=tasks,
            strategy=self.interleave_strategy,
        )

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Interleaved Batch: {result.batch_id}")
            print(f"Tasks: {len(tasks)} | Strategy: {self.interleave_strategy}")
            print(f"Max turns: {self.config.max_turns_per_session}")
            print(f"{'='*60}\n")

        # ============================================================
        # Build global image index mapping
        # ============================================================
        # VNF has 4 images (Image 0-3), RC has 3 (Image 4-6), AC has 3 (Image 7-9)
        global_image_offset = 0
        task_image_offsets: Dict[str, int] = {}
        task_image_counts: Dict[str, int] = {}

        for task in tasks:
            task_id = task.get("task_id", str(id(task)))
            n_images = len(task.get("images", []))
            task_image_offsets[task_id] = global_image_offset
            task_image_counts[task_id] = n_images
            global_image_offset += n_images

        if self.verbose:
            print(f"[Global Image Index] Total images: {global_image_offset}")
            for tid, offset in task_image_offsets.items():
                count = task_image_counts[tid]
                print(f"  {tid}: Image {offset} - Image {offset + count - 1}")
            print()

        # ============================================================
        # Rewrite task data with global image labels
        # ============================================================
        rewritten_tasks: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            task_id = task.get("task_id", str(id(task)))
            offset = task_image_offsets[task_id]
            n_images = task_image_counts[task_id]

            # Deep copy to avoid mutating original
            rewritten = dict(task)

            # Rewrite answer: "Image 0" → "Image {offset}", etc.
            answer = str(rewritten.get("answer", ""))
            for local_idx in range(n_images - 1, -1, -1):  # reverse to avoid "Image 1" matching in "Image 10"
                global_idx = offset + local_idx
                answer = answer.replace(f"Image {local_idx}", f"Image {global_idx}")
            rewritten["answer"] = answer

            # Rewrite question similarly
            question = str(rewritten.get("question", ""))
            for local_idx in range(n_images - 1, -1, -1):
                global_idx = offset + local_idx
                question = question.replace(f"Image {local_idx}", f"Image {global_idx}")
            rewritten["question"] = question

            # Store the global offset for the simulator to use
            rewritten["_global_image_offset"] = offset

            rewritten_tasks[task_id] = rewritten

        # ============================================================
        # Create a StatefulStrategicSimulator per task
        # ============================================================
        simulators: Dict[str, StatefulStrategicSimulator] = {}
        task_map: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            task_id = task.get("task_id", str(id(task)))
            sim = StatefulStrategicSimulator(
                llm_client=self.llm_client,
                evaluator=StateAwareEvaluator(),
                max_turns_per_task=self.config.max_turns_per_task,
                min_turns_per_task=self.config.min_turns_per_task,
                verbose=self.verbose,
                # Key: only send images on the first turn of each task
                image_injection_policy=ImageInjectionPolicy.SEND_ALL_FIRST_TURN,
                **self.config.simulator_kwargs,
            )
            # Tell the simulator its global image offset for label rewriting
            sim._global_image_offset = task_image_offsets[task_id]
            sim._global_image_count = task_image_counts[task_id]
            simulators[task_id] = sim
            task_map[task_id] = rewritten_tasks[task_id]

            # Register in shared window
            self.shared_window.register_task(task_id, {
                "task_type": task.get("task_type", ""),
                "question": rewritten_tasks[task_id].get("question", ""),
                "image_offset": task_image_offsets[task_id],
                "image_count": task_image_counts[task_id],
            })

        # --- Main interleaved loop ---
        active_task_id: Optional[str] = None
        phase_turn_count = 0

        while not self.shared_window.is_exhausted:
            segment = self.scheduler.next_segment()
            if segment is None:
                break  # all tasks/phases done

            task_id, phase_name = segment
            sim = simulators[task_id]
            task = task_map[task_id]

            if self.verbose:
                print(f"\n>>> Segment: task={task_id}, phase={phase_name}")

            # Start task if not yet started
            if sim.task_state is None:
                sim.start_task(task)

            # Run this phase's turns
            turns_in_segment = self._run_phase_segment(
                sim=sim,
                task_id=task_id,
                phase_name=phase_name,
            )

            # Record in shared window (with global image labels)
            offset = task_image_offsets[task_id]
            n_img = task_image_counts[task_id]
            for turn_entry in sim.conversation_history[-turns_in_segment:]:
                entry = dict(turn_entry)
                # Rewrite local "Image X" references in query/response to global
                for field in ("query", "response"):
                    text = str(entry.get(field, ""))
                    for local_idx in range(n_img - 1, -1, -1):
                        text = text.replace(f"Image {local_idx}", f"Image {offset + local_idx}")
                    entry[field] = text
                self.shared_window.add_turn(task_id, entry)

            self.total_turns += turns_in_segment

            # Report phase done
            self.scheduler.report_phase_done(task_id, phase_name)

            if self.shared_window.is_exhausted:
                if self.verbose:
                    print(f"[Batch] Max turns reached ({self.config.max_turns_per_session})")
                break

        # --- Compile results ---
        result.total_turns = self.total_turns
        result.end_time = datetime.now()

        for task_id, sim in simulators.items():
            task_result_payload: Dict[str, Any] = {}
            if hasattr(sim, '_generate_task_report') and sim.task_state is not None:
                try:
                    task_result_payload = sim._generate_task_report(
                        getattr(sim, 'conversation_history', []),
                        {},
                    )
                except Exception as exc:
                    logger.warning("[InterleavedBatch] Failed to build task report for %s: %s", task_id, exc)
                    task_result_payload = {}

            official_report = self._extract_official_report(
                task_result_payload,
                fallback_reason='missing_interleaved_official_report',
            )
            runtime_payload = task_result_payload.get('runtime', {}) if isinstance(task_result_payload.get('runtime'), dict) else {}
            aggregate_scores = task_result_payload.get('scores', {}).get('aggregate', {}) if isinstance(task_result_payload.get('scores'), dict) else {}

            task_result = {
                "task_id": task_id,
                "task_type": task_map[task_id].get("task_type", ""),
                "turns_used": sim.turn_count,
                "completed": sim.task_state is not None
                and sim.task_state.current_phase.phase_complete
                if sim.task_state
                else False,
                "image_range": f"Image {task_image_offsets[task_id]} - Image {task_image_offsets[task_id] + task_image_counts[task_id] - 1}",
                "scores": aggregate_scores,
                "runtime": runtime_payload,
                "official_report": official_report,
                "full_result": task_result_payload,
                "turns": getattr(sim, 'conversation_history', []).copy(),
                "conversation_history": getattr(sim, 'conversation_history', []).copy(),
            }

            # Include state report if available
            state_report = sim.get_state_report()
            if state_report:
                task_result["state_report"] = state_report

            result.task_results.append(task_result)
            result.turns_per_task.append(sim.turn_count)

            if task_result.get("completed"):
                result.tasks_completed += 1

        result.conversation_log = self.shared_window.full_history
        result.aggregate_scores = self._calculate_aggregate_scores(result.task_results)

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Batch complete: {result.tasks_completed}/{result.tasks_attempted} tasks")
            print(f"Total turns: {result.total_turns}")
            print(f"{'='*60}")

        return result

    def _run_phase_segment(
        self,
        sim: StatefulStrategicSimulator,
        task_id: str,
        phase_name: str,
    ) -> int:
        """
        Execute turns for one task's one phase.

        Runs until the phase's min_turns are met or the phase advances.
        Returns the number of turns executed.
        """
        if sim.task_state is None:
            return 0

        initial_turn = sim.turn_count
        strategy = TASK_STRATEGIES.get(sim.task_state.task_type)

        # Find min_turns for this phase
        min_turns = 2  # default
        if strategy:
            for pc in strategy.phases:
                if pc["name"] == phase_name:
                    min_turns = pc.get("min_turns", 2)
                    break

        turns_done = 0
        while turns_done < min_turns:
            if self.shared_window and self.shared_window.is_exhausted:
                break

            try:
                step_result = sim.step()
                turns_done += 1
            except Exception as e:
                logger.error(f"[InterleavedBatch] Error in step for {task_id}: {e}")
                break

            # Check if phase advanced naturally
            current_phase = sim.task_state.current_phase.phase_name if sim.task_state else ""
            if current_phase != phase_name:
                # Phase has naturally advanced — we're done with this segment
                break

            # Check if task is done
            if not step_result.get("should_continue", True):
                break

        return sim.turn_count - initial_turn
