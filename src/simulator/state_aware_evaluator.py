"""
State-Aware Evaluator — Stub
=============================

Minimal stub that extends the existing Evaluator with state-tracking
hooks. Full implementation is defined in the state evaluation
improvement doc. This stub ensures imports from stateful_simulator.py
and interleaved_batch.py don't break.

Safety:
  - Evaluator's existing code is not modified
  - All overrides call super() first
  - If no state_schema is registered, behaves identically to Evaluator
"""

from typing import Dict, List, Any, Optional
import logging

from .evaluator import Evaluator, EvaluationMode
from .state_schema_types import StateSchema

logger = logging.getLogger(__name__)


class StateAwareEvaluator(Evaluator):
    """
    Evaluator subclass that adds state-variable-level tracking.

    Extended capabilities (over base Evaluator):
      - register_state_schema(): accept a StateSchema for the current task
      - record_state_event(): log variable-level observation/challenge events
      - get_state_report(): generate state-evolution report

    Graceful degradation:
      - If no state_schema is registered, all new methods are no-ops
      - All existing Evaluator methods work identically via super()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state_schema: Optional[StateSchema] = None
        self._state_events: List[Dict[str, Any]] = []

    def register_state_schema(self, schema: StateSchema):
        """Register a state schema for the current task."""
        self._state_schema = schema
        logger.info(
            f"[StateAwareEvaluator] Registered schema with "
            f"{len(schema.variables)} variables, "
            f"{len(schema.probing_variables)} probing variables"
        )

    def record_state_event(
        self,
        turn: int,
        event_type: str,
        variable_name: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Record a state-variable event.

        Args:
            turn: Turn number
            event_type: 'observed' | 'challenged' | 'probed' | 'forgotten'
            variable_name: Name of the variable in state_schema
            details: Optional extra information
        """
        if self._state_schema is None:
            return  # graceful degradation

        event = {
            "turn": turn,
            "event_type": event_type,
            "variable_name": variable_name,
            "details": details or {},
        }
        self._state_events.append(event)
        logger.debug(f"[StateAwareEvaluator] Event: {event_type} on {variable_name} at turn {turn}")

    def get_state_report(self) -> Dict[str, Any]:
        """Generate a summary report of state evolution."""
        if self._state_schema is None:
            return {
                "status": "no_schema_registered",
                "total_events": 0,
                "variables_touched": 0,
                "variables_total": 0,
                "probing_variables_total": 0,
                "coverage": 0.0,
                "events": [],
            }

        # Group events by variable
        by_variable: Dict[str, List[Dict]] = {}
        for evt in self._state_events:
            vname = evt["variable_name"]
            by_variable.setdefault(vname, []).append(evt)

        return {
            "status": "registered",
            "total_events": len(self._state_events),
            "variables_touched": len(by_variable),
            "variables_total": len(self._state_schema.variables),
            "probing_variables_total": len(self._state_schema.probing_variables),
            "coverage": len(by_variable) / len(self._state_schema.variables)
            if self._state_schema.variables else 0,
            "events_by_variable": by_variable,
        }

    def reset_for_task(self, *args, **kwargs):
        """Override: reset state tracking on top of base reset."""
        super().reset_for_task(*args, **kwargs)
        self._state_schema = None
        self._state_events = []