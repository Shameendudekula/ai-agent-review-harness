"""Provider-independent planner interface."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.app.agent.schema import PlanningContext


class PlannerError(Exception):
    """The planner could not produce output (provider failure, timeout, refusal).

    The message is stored and shown to users, so it must not contain secrets.
    """


@dataclass
class PlannerOutput:
    # Raw, unvalidated plan as produced by the planner (e.g. parsed JSON).
    raw_plan: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class Planner(Protocol):
    name: str

    def plan(self, context: PlanningContext) -> PlannerOutput:
        """Return a raw plan for validation. Must not execute anything."""
        ...
