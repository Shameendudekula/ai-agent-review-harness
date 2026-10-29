"""The structured plan every planner must return, and the context it receives.

Planner output is untrusted. It is parsed into ``AgentPlan`` before anything is
stored; output that fails validation is recorded as a failed planning attempt.

Note what the schema does *not* contain: there is no field through which a plan can
mark itself approved, authorized, or safe. ``agent_risk_estimate`` is recorded for
transparency but the policy engine may only raise it, never lower it.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.domain.enums import AssumptionBasis, RiskLevel, RunTrigger
from backend.app.tools.verification import VerificationCriterion

Key = str


class PlannedAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    statement: str = Field(min_length=1, max_length=500)
    basis: AssumptionBasis
    evidence: str | None = Field(default=None, max_length=500)
    consequence_if_wrong: str = Field(min_length=1, max_length=500)


class PlannedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    description: str = Field(min_length=1, max_length=500)
    # Any string: whether the tool is allowed is decided by policy, not by parsing.
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1000)
    expected_outcome: str = Field(min_length=1, max_length=500)
    verification: list[VerificationCriterion] = Field(min_length=1, max_length=10)
    depends_on_assumptions: list[Key] = Field(default_factory=list, max_length=10)
    agent_risk_estimate: RiskLevel = RiskLevel.LOW

    @field_validator("arguments")
    @classmethod
    def limit_argument_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 20 or len(repr(value)) > 4000:
            raise ValueError("arguments are too large")
        return value

    @field_validator("agent_risk_estimate")
    @classmethod
    def agent_cannot_declare_forbidden(cls, value: RiskLevel) -> RiskLevel:
        if value == RiskLevel.FORBIDDEN:
            raise ValueError("FORBIDDEN is assigned by policy, not by the agent")
        return value


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    steps: list[str] = Field(min_length=1, max_length=15)
    assumptions: list[PlannedAssumption] = Field(default_factory=list, max_length=15)
    open_questions: list[str] = Field(default_factory=list, max_length=5)
    actions: list[PlannedAction] = Field(min_length=1, max_length=10)

    @field_validator("steps", "open_questions")
    @classmethod
    def non_empty_strings(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in value):
            raise ValueError("items must be non-empty strings of at most 500 characters")
        return value

    @model_validator(mode="after")
    def check_references(self) -> "AgentPlan":
        assumption_keys = [a.key for a in self.assumptions]
        action_keys = [a.key for a in self.actions]
        if len(set(assumption_keys)) != len(assumption_keys):
            raise ValueError("assumption keys must be unique")
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("action keys must be unique")
        known = set(assumption_keys)
        for action in self.actions:
            unknown = set(action.depends_on_assumptions) - known
            if unknown:
                raise ValueError(f"action '{action.key}' references unknown assumptions: {sorted(unknown)}")
        return self


class ReviewerMessage(BaseModel):
    trigger: RunTrigger
    message: str


class PlanningContext(BaseModel):
    """Everything a planner is allowed to see. Built by the backend, not by the client."""

    task_title: str
    task_description: str
    attempt_number: int
    trigger: RunTrigger
    # All reviewer feedback and clarifications so far, oldest first.
    reviewer_messages: list[ReviewerMessage] = Field(default_factory=list)
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
