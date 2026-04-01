"""
Task Progress Tracking
======================

Provides structured progress tracking for individual tasks and their
phases. Used by StatefulStrategicSimulator and InterleavedBatchSimulator
to support:
  - Phase-level pause/resume (for interleaved scheduling)
  - Variable coverage tracking (from state_schema)
  - Sub-goal completion awareness

Safety:
  - Independent new module — does not modify StrategicSimulator's TaskState
  - Composed into StatefulStrategicSimulator, not inherited
  - Works without state_schema (empty tracked_variables → coverage = 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .state_schema_types import StateSchema


@dataclass
class PhaseCompletion:
    """Completion state for a single phase within a task."""

    phase_name: str
    status: str = "not_started"
    # 'not_started' | 'in_progress' | 'paused' | 'completed'

    min_turns: int = 2
    turns_used: int = 0

    variables_observed: List[str] = field(default_factory=list)
    # Variables observed (mentioned by model) during this phase

    variables_probed: List[str] = field(default_factory=list)
    # Variables explicitly probed during this phase

    probe_results: Dict[str, bool] = field(default_factory=dict)
    # variable_name -> whether model answered correctly

    can_pause: bool = False
    # Whether this phase can be safely paused for interleaving

    def check_pausable(self) -> bool:
        """
        Determine if this phase has met minimum requirements to pause.

        A phase is pausable when:
          1. At least min_turns have been executed
          2. At least one variable has been observed (if tracking is active)
        """
        self.can_pause = (
            self.turns_used >= self.min_turns
            and (len(self.variables_observed) > 0 or self.min_turns == 0)
        )
        return self.can_pause

    def record_turn(self):
        """Record that a turn has been executed in this phase."""
        self.turns_used += 1
        if self.status == "not_started":
            self.status = "in_progress"

    def record_observation(self, variable_name: str):
        """Record that a variable was observed in this phase."""
        if variable_name not in self.variables_observed:
            self.variables_observed.append(variable_name)

    def record_probe(self, variable_name: str, correct: bool):
        """Record a probe result for a variable."""
        if variable_name not in self.variables_probed:
            self.variables_probed.append(variable_name)
        self.probe_results[variable_name] = correct

    def complete(self):
        """Mark this phase as completed."""
        self.status = "completed"

    def pause(self):
        """Pause this phase (for interleaved scheduling)."""
        if self.status == "in_progress":
            self.status = "paused"

    def resume(self):
        """Resume a paused phase."""
        if self.status == "paused":
            self.status = "in_progress"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_name": self.phase_name,
            "status": self.status,
            "min_turns": self.min_turns,
            "turns_used": self.turns_used,
            "variables_observed": self.variables_observed,
            "variables_probed": self.variables_probed,
            "probe_results": self.probe_results,
            "can_pause": self.can_pause,
        }


@dataclass
class TaskProgress:
    """
    Complete progress tracker for a single task.

    Composed into StatefulStrategicSimulator — does NOT replace or modify
    the original TaskState dataclass.
    """

    task_id: str
    task_type: str
    phases: List[PhaseCompletion] = field(default_factory=list)
    current_phase_index: int = 0
    overall_status: str = "not_started"
    # 'not_started' | 'in_progress' | 'paused' | 'completed' | 'failed'

    tracked_variables: Dict[str, Any] = field(default_factory=dict)
    # variable_name -> expected value (loaded from state_schema)

    @classmethod
    def from_state_schema(
        cls,
        task_id: str,
        task_type: str,
        schema: Optional[StateSchema],
        phase_configs: List[Dict[str, Any]],
    ) -> "TaskProgress":
        """
        Initialize from a StateSchema and phase configuration list.

        Args:
            task_id: Unique task identifier
            task_type: Task type string (e.g. 'attribute_comparison')
            schema: StateSchema from data annotation (may be None)
            phase_configs: List of phase dicts from TASK_STRATEGIES
                           Each dict has: name, description, actions, min_turns, goal
        """
        phases = []
        for pc in phase_configs:
            phases.append(PhaseCompletion(
                phase_name=pc.get("name", "unknown"),
                min_turns=pc.get("min_turns", 2),
            ))

        tracked = {}
        if schema and schema.variables:
            tracked = {name: var.value for name, var in schema.variables.items()}

        return cls(
            task_id=task_id,
            task_type=task_type,
            phases=phases,
            current_phase_index=0,
            overall_status="not_started",
            tracked_variables=tracked,
        )

    # --- Phase navigation ---

    @property
    def current_phase(self) -> Optional[PhaseCompletion]:
        """Get current phase, or None if all phases are done."""
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None

    def is_phase_pausable(self) -> bool:
        """Can the current phase be safely paused for interleaving?"""
        phase = self.current_phase
        if phase is None:
            return False
        return phase.check_pausable()

    def advance_to_next_phase(self) -> bool:
        """
        Move to the next phase. Returns True if advanced, False if
        already at the last phase.
        """
        current = self.current_phase
        if current is None:
            return False

        current.complete()
        next_idx = self.current_phase_index + 1

        if next_idx >= len(self.phases):
            # All phases done
            self.overall_status = "completed"
            return False

        self.current_phase_index = next_idx
        self.phases[next_idx].status = "in_progress"
        return True

    def pause_current_phase(self):
        """Pause the current phase (for interleaved scheduling)."""
        current = self.current_phase
        if current:
            current.pause()
        self.overall_status = "paused"

    def resume_current_phase(self):
        """Resume the current (paused) phase."""
        current = self.current_phase
        if current:
            current.resume()
        self.overall_status = "in_progress"

    # --- Variable coverage ---

    def get_variable_coverage(self) -> float:
        """
        Fraction of tracked variables that have been observed
        across all phases so far.
        """
        if not self.tracked_variables:
            return 0.0

        all_observed = set()
        for phase in self.phases:
            all_observed.update(phase.variables_observed)

        return len(all_observed) / len(self.tracked_variables)

    def get_probe_accuracy(self) -> float:
        """
        Average probe accuracy across all phases.
        Returns 0 if no probes have been done.
        """
        all_results: List[bool] = []
        for phase in self.phases:
            all_results.extend(phase.probe_results.values())

        if not all_results:
            return 0.0
        return sum(1 for r in all_results if r) / len(all_results)

    # --- Recording ---

    def record_turn(self):
        """Record a turn in the current phase."""
        if self.overall_status == "not_started":
            self.overall_status = "in_progress"
        current = self.current_phase
        if current:
            current.record_turn()

    def record_observation(self, variable_name: str):
        """Record that a variable was observed in the current phase."""
        current = self.current_phase
        if current:
            current.record_observation(variable_name)

    def record_probe(self, variable_name: str, correct: bool):
        """Record a probe result in the current phase."""
        current = self.current_phase
        if current:
            current.record_probe(variable_name, correct)

    # --- Serialization ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "overall_status": self.overall_status,
            "current_phase_index": self.current_phase_index,
            "phases": [p.to_dict() for p in self.phases],
            "variable_coverage": self.get_variable_coverage(),
            "probe_accuracy": self.get_probe_accuracy(),
        }

    def __repr__(self) -> str:
        phase_name = self.current_phase.phase_name if self.current_phase else "done"
        return (
            f"TaskProgress(id={self.task_id!r}, type={self.task_type!r}, "
            f"status={self.overall_status!r}, phase={phase_name}, "
            f"coverage={self.get_variable_coverage():.1%})"
        )
