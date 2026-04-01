"""
Stateful Strategic Simulator
=============================

Subclass of StrategicSimulator that adds:
  1. State-schema-aware ground truth loading
  2. State event recording per turn
  3. Modular prompt assembly via PromptRouter
  4. TaskProgress tracking for phase-level pause/resume

Safety guarantees:
  - StrategicSimulator's code is NOT modified
  - All overrides call super() first, then append new logic
  - If state_schema is absent, every override degrades to super() behavior
  - Can be swapped back to StrategicSimulator with zero code changes elsewhere

Cross-doc dependencies:
  - state_schema_types.py  (data annotation improvement — stub provided)
  - state_aware_evaluator.py (state evaluation improvement — stub provided)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .strategic_simulator import StrategicSimulator
from .state_schema_types import StateSchema, StateVariable
from .state_aware_evaluator import StateAwareEvaluator
from .task_progress import TaskProgress
from .prompt_router import PromptRouter
from .action_space import TASK_STRATEGIES

logger = logging.getLogger(__name__)


class StatefulStrategicSimulator(StrategicSimulator):
    """
    StrategicSimulator subclass with state-schema awareness.

    Extension points (all override super() first):
      1. __init__       — compose TaskProgress + PromptRouter
      2. _extract_ground_truths(task) — load state_schema if present
      3. step()         — append state event recording after base logic
      4. _build_core_system_prompt(allowed_actions) — delegate to PromptRouter
      5. _build_core_user_prompt() — delegate to PromptRouter

    Graceful degradation:
      If task has no 'state_schema' field, this class behaves identically
      to the base StrategicSimulator (all new logic is guarded by
      ``if self._state_schema``).
    """

    def __init__(self, *args, **kwargs):
        # If caller didn't provide an evaluator, use StateAwareEvaluator
        if "evaluator" not in kwargs or kwargs["evaluator"] is None:
            kwargs["evaluator"] = StateAwareEvaluator()

        super().__init__(*args, **kwargs)

        # --- New composition ---
        self.task_progress: Optional[TaskProgress] = None
        self.prompt_router: PromptRouter = PromptRouter()
        self._state_schema: Optional[StateSchema] = None

        # Interleaved batch context (set by InterleavedBatchSimulator)
        self._global_image_offset: int = 0
        self._global_image_count: int = 0

        # State tracking log — always populated, even without state_schema
        self._state_tracking_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Override: _extract_ground_truths
    # ------------------------------------------------------------------

    def _extract_ground_truths(self, task: Dict[str, Any]):
        """
        Override: base extraction + state_schema loading + TaskProgress init.

        Flow:
          1. super()._extract_ground_truths(task)  — keeps all original logic
          2. Always initialize TaskProgress (even without state_schema)
          3. If task['state_schema'] exists, register it
        """
        super()._extract_ground_truths(task)

        # --- Sanitize expected_answer: strip unobservable metrics ---
        if self.task_state and self.task_state.expected_answer:
            original = self.task_state.expected_answer
            sanitized = self._sanitize_expected_answer(original)
            if sanitized != original:
                self.task_state.expected_answer = sanitized
                # Also update ground_truths dict
                self.task_state.ground_truths["expected_answer"] = sanitized
                # Re-register in evaluator
                self.evaluator.register_key_fact(
                    "expected_answer", sanitized, source="task"
                )
                logger.info(
                    f"[StatefulSimulator] Sanitized expected_answer: "
                    f"'{original}' → '{sanitized}'"
                )

        # Always init TaskProgress for phase tracking
        strategy = self._get_strategy(task.get("task_type", ""))
        phase_configs = strategy.phases if strategy else []

        # --- Load state_schema if present ---
        schema_data = task.get("state_schema")
        if schema_data:
            self._state_schema = StateSchema.from_dict(schema_data)

            # Register in evaluator (if it's the state-aware variant)
            if isinstance(self.evaluator, StateAwareEvaluator):
                self.evaluator.register_state_schema(self._state_schema)

            logger.info(
                f"[StatefulSimulator] Loaded state_schema with "
                f"{len(self._state_schema.variables)} variables for task "
                f"{task.get('task_id', '?')}"
            )

        self.task_progress = TaskProgress.from_state_schema(
            task_id=task.get("task_id", ""),
            task_type=task.get("task_type", ""),
            schema=self._state_schema,  # may be None — that's fine
            phase_configs=phase_configs,
        )

        # Log initial state
        self._state_tracking_log.append({
            "event": "task_init",
            "task_id": task.get("task_id", ""),
            "task_type": task.get("task_type", ""),
            "has_state_schema": self._state_schema is not None,
            "n_phases": len(self.task_progress.phases),
            "n_tracked_variables": len(self.task_progress.tracked_variables),
            "global_image_offset": self._global_image_offset,
            "global_image_range": f"Image {self._global_image_offset} - Image {self._global_image_offset + self._global_image_count - 1}" if self._global_image_count > 0 else "N/A",
        })

    # ------------------------------------------------------------------
    # Override: step
    # ------------------------------------------------------------------

    def step(self) -> Dict[str, Any]:
        """
        Override: base step + state event recording + tracking log.

        Flow:
          1. result = super().step()       — full original turn logic
          2. Record state events (if state_schema exists)
          3. Update TaskProgress (always)
          4. Append to state tracking log (always)
          5. Return original result dict (unchanged format)
        """
        result = super().step()

        # --- Sync TaskProgress phase with parent's phase ---
        if self.task_progress and self.task_state:
            parent_phase = self.task_state.current_phase.phase_name
            tp_phase = self.task_progress.current_phase
            if tp_phase and tp_phase.phase_name != parent_phase:
                # Parent has advanced — sync TaskProgress forward
                while (self.task_progress.current_phase
                       and self.task_progress.current_phase.phase_name != parent_phase):
                    if not self.task_progress.advance_to_next_phase():
                        break  # no more phases

        # --- State tracking (always, even without schema) ---
        if self.task_progress:
            self.task_progress.record_turn()

        # --- State event recording (only with schema) ---
        if self._state_schema and self.task_progress:
            self._record_state_events(result)

        # --- Always log turn state ---
        phase_name = result.get("phase", "?")
        turn_log = {
            "event": "turn",
            "turn": result.get("turn", self.turn_count),
            "global_turn": self.turn_count,
            "phase": phase_name,
            "action": result.get("action", ""),
            "score": result.get("evaluation", {}).get("score", 0),
            "new_images_sent_count": result.get("new_images_sent_count", len(result.get("images_sent", []) or [])),
            "visible_image_refs": result.get("visible_image_refs", []),
            "memory_image_refs": result.get("memory_image_refs", []),
            "turn_input_mode": result.get("turn_input_mode", "text_only"),
            "images_sent_count_legacy": result.get("images_sent_count_legacy", len(result.get("images_sent", []) or [])),
            "evaluation_validity": result.get("evaluation_validity", result.get("evaluation", {}).get("evaluation_validity", "valid")),
            "image_delivery": result.get("image_delivery", {}),
            "should_continue": result.get("should_continue", True),
        }

        if self.task_progress:
            current = self.task_progress.current_phase
            turn_log["phase_status"] = current.status if current else "done"
            turn_log["phase_turns"] = f"{current.turns_used}/{current.min_turns}" if current else "N/A"
            turn_log["variable_coverage"] = f"{self.task_progress.get_variable_coverage():.0%}"
            turn_log["overall_status"] = self.task_progress.overall_status

        self._state_tracking_log.append(turn_log)

        return result

    # ------------------------------------------------------------------
    # Override: _build_core_system_prompt
    # ------------------------------------------------------------------

    def _build_core_system_prompt(self, allowed_actions: List[str]) -> str:
        """
        Override: always delegate to PromptRouter for improved prompts.
        PromptRouter provides evidence-driven strategy guidance and
        phase-specific instructions that the base prompt lacks.
        """
        state_context = {}
        if self._state_schema:
            state_context["probing_variables"] = self._state_schema.probing_variables

        system, _ = self.prompt_router.assemble_prompt(
            task_type=self.task_state.task_type if self.task_state else "",
            phase=self.task_state.current_phase.phase_name if self.task_state else "",
            difficulty=self.task_state.difficulty_level if self.task_state else 1,
            turn_count=self.turn_count,
            vlm_response="",
            history=[],
            state_context=state_context,
            allowed_actions=allowed_actions,
        )
        return system

    # ------------------------------------------------------------------
    # Override: _build_core_user_prompt
    # ------------------------------------------------------------------

    def _build_core_user_prompt(self) -> str:
        """
        Override: always delegate to PromptRouter for improved prompts.
        """
        # Get recent VLM response from memory
        last_response = ""
        if self.memory.current_task and self.memory.current_task.turns:
            last_response = self.memory.current_task.turns[-1].model_response or ""

        # Build history entries from memory
        history_entries = []
        if self.memory.current_task and self.memory.current_task.turns:
            for turn in self.memory.current_task.turns[-5:]:
                history_entries.append({
                    "action": turn.action,
                    "user_message": turn.user_message,
                    "model_response": turn.model_response,
                })

        state_context = {}
        if self._state_schema:
            state_context["probing_variables"] = self._state_schema.probing_variables

        _, user = self.prompt_router.assemble_prompt(
            task_type=self.task_state.task_type if self.task_state else "",
            phase=self.task_state.current_phase.phase_name if self.task_state else "",
            difficulty=self.task_state.difficulty_level if self.task_state else 1,
            turn_count=self.turn_count,
            vlm_response=last_response,
            history=history_entries,
            state_context=state_context,
        )
        return user

    # ------------------------------------------------------------------
    # New private methods (no parent override)
    # ------------------------------------------------------------------

    def _record_state_events(self, step_result: Dict[str, Any]):
        """
        After each turn, scan the model's response for mentions of
        state variables and record events in the evaluator.
        """
        if not isinstance(self.evaluator, StateAwareEvaluator):
            return

        turn = step_result.get("turn", self.turn_count)
        action = step_result.get("action", "")
        response = step_result.get("response", "")

        # Determine event type from action
        if action in ("mislead", "mislead_subtle", "cross_image_confusion",
                       "memory_injection", "inconsistency_injection"):
            event_type = "challenged"
        elif action in ("consistency_check", "redundancy"):
            event_type = "probed"
        else:
            event_type = "observed"

        # Check each variable for mentions in the response
        for var_name, var in self._state_schema.variables.items():
            if self._is_variable_mentioned(response, var):
                self.evaluator.record_state_event(turn, event_type, var_name)
                if self.task_progress:
                    self.task_progress.record_observation(var_name)

    def _is_variable_mentioned(self, response: str, var: StateVariable) -> bool:
        """
        Check whether the model's response mentions a state variable.

        Uses a simple keyword-matching heuristic:
          1. Check var.keywords (explicit keyword list)
          2. Check var.value (string representation)
          3. Check var.description words

        This is intentionally simple — a more sophisticated NLI-based
        approach can replace this later without changing the interface.
        """
        if not response:
            return False

        response_lower = response.lower()

        # 1. Explicit keywords
        if var.keywords:
            for kw in var.keywords:
                if kw.lower() in response_lower:
                    return True

        # 2. Value mention
        if var.value is not None:
            value_str = str(var.value).lower()
            if len(value_str) >= 2 and value_str in response_lower:
                return True

        # 3. Description keywords (words >= 3 chars)
        if var.description:
            desc_words = [
                w.lower() for w in var.description.split()
                if len(w) >= 3
            ]
            # Require at least 2 description words to match
            matches = sum(1 for w in desc_words if w in response_lower)
            if len(desc_words) > 0 and matches >= min(2, len(desc_words)):
                return True

        return False

    # ------------------------------------------------------------------
    # Answer sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_expected_answer(answer: str) -> str:
        """
        Strip unobservable quantitative metrics from expected_answer.

        Examples:
          "Image 1 with 64 potential relationships" → "Image 1"
          "Image 0 with 12 objects"                 → "Image 0"
          "Image 2 with 5 different types: a, b, c" → "Image 2"
          "Image 0 with question length 42"         → "Image 0"
          "Image 3"                                 → "Image 3" (unchanged)
          "The red car"                             → "The red car" (unchanged)

        Only strips the "with ..." suffix when the answer starts with
        "Image N" — other answer formats are left untouched.
        """
        # Pattern: "Image <N> with <anything>"
        match = re.match(r'^(Image\s+\d+)\s+with\s+.+$', answer, re.IGNORECASE)
        if match:
            return match.group(1)
        return answer

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_state_report(self) -> Dict[str, Any]:
        """Get combined state report from evaluator, task progress, and tracking log."""
        report: Dict[str, Any] = {}

        if isinstance(self.evaluator, StateAwareEvaluator):
            report["evaluator_state"] = self.evaluator.get_state_report()

        if self.task_progress:
            report["task_progress"] = self.task_progress.to_dict()

        # Always include tracking log
        report["tracking_log"] = self._state_tracking_log

        return report
