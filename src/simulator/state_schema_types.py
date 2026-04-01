"""
State Schema Types — Shared Type Definitions
=============================================

Minimal stub providing the types needed by other modules in the
dialogue/evaluation improvement pipeline. This file is the "shared
foundation" consumed by:
  - task_progress.py
  - stateful_simulator.py
  - state_aware_evaluator.py
  - prompt_router.py

Full implementation is defined in the data annotation improvement doc.
This stub ensures imports don't break before that doc is implemented.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class StateVariable:
    """A single trackable variable in a task's state schema."""
    name: str
    value: Any = None
    var_type: str = "unknown"  # 'count', 'boolean', 'position', 'object_list', 'derived', etc.
    source: str = ""           # e.g. 'image_0', 'image_1'
    relevance: str = "primary"  # 'primary' | 'auxiliary'
    observable_from: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    # Keywords used for simple mention-detection in model responses
    keywords: List[str] = field(default_factory=list)


@dataclass
class StateSchema:
    """
    Structured state schema for a task.

    Contains all trackable variables, their dependencies,
    and metadata for probing/evaluation.
    """
    variables: Dict[str, StateVariable] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    final_question_variables: List[str] = field(default_factory=list)
    probing_variables: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSchema":
        """Deserialize from a dict (e.g. loaded from JSON task data)."""
        variables = {}
        for name, var_data in data.get("variables", {}).items():
            variables[name] = StateVariable(
                name=name,
                value=var_data.get("value"),
                var_type=var_data.get("type", "unknown"),
                source=var_data.get("source", ""),
                relevance=var_data.get("relevance", "primary"),
                observable_from=var_data.get("observable_from", []),
                depends_on=var_data.get("depends_on", []),
                description=var_data.get("description", ""),
                keywords=var_data.get("keywords", []),
            )
        return cls(
            variables=variables,
            dependencies=data.get("dependencies", {}),
            final_question_variables=data.get("final_question_variables", []),
            probing_variables=data.get("probing_variables", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "variables": {
                name: {
                    "value": v.value,
                    "type": v.var_type,
                    "source": v.source,
                    "relevance": v.relevance,
                    "observable_from": v.observable_from,
                    "depends_on": v.depends_on,
                    "description": v.description,
                    "keywords": v.keywords,
                }
                for name, v in self.variables.items()
            },
            "dependencies": self.dependencies,
            "final_question_variables": self.final_question_variables,
            "probing_variables": self.probing_variables,
        }