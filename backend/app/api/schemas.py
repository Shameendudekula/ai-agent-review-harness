"""Request and response models for the public API."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.domain.enums import (
    Actor,
    AssumptionBasis,
    AuthorizationState,
    DecisionType,
    EventType,
    ExecutionState,
    FailureStage,
    ReviewMode,
    ReviewState,
    RiskLevel,
    RunStatus,
    RunTrigger,
    TaskStatus,
    VerificationState,
)


class StrictRequest(BaseModel):
    # Unknown fields are rejected, so a client cannot smuggle in e.g. "approved": true.
    model_config = ConfigDict(extra="forbid")


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class TaskCreate(StrictRequest):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    review_mode: ReviewMode = ReviewMode.STRUCTURED

    @field_validator("title", "description")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class CancelRequest(StrictRequest):
    reason: str | None = Field(default=None, max_length=1000)


class ReviewDecisionCreate(StrictRequest):
    decision: DecisionType
    action_id: uuid.UUID | None = None
    rationale: str | None = Field(default=None, max_length=2000)
    reviewer: str = Field(default="demo-reviewer", min_length=1, max_length=80,
                          pattern=r"^[A-Za-z0-9 ._@-]+$")

    @model_validator(mode="after")
    def rationale_required_for_feedback(self) -> "ReviewDecisionCreate":
        self.rationale = _strip(self.rationale)
        if self.decision != DecisionType.APPROVE and not self.rationale:
            raise ValueError(f"rationale is required for {self.decision}")
        return self


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssumptionOut(ORMModel):
    id: uuid.UUID
    key: str
    statement: str
    basis: AssumptionBasis
    evidence: str | None
    consequence_if_wrong: str


class ActionOut(ORMModel):
    id: uuid.UUID
    sequence: int
    key: str
    description: str
    tool_name: str
    arguments: dict[str, Any]
    rationale: str
    expected_outcome: str
    verification_criteria: list[dict[str, Any]]
    depends_on_assumptions: list[str]
    agent_risk_estimate: RiskLevel
    risk_level: RiskLevel
    risk_factors: list[str]
    review_required: bool
    review_reasons: list[str]
    review_state: ReviewState
    authorization_state: AuthorizationState
    authorization_reason: str | None
    execution_state: ExecutionState
    execution_result: dict[str, Any] | None
    execution_error: str | None
    verification_state: VerificationState
    verification_details: list[dict[str, Any]] | None


class RunSummaryOut(ORMModel):
    id: uuid.UUID
    attempt_number: int
    trigger: RunTrigger
    reviewer_input: str | None
    planner: str
    status: RunStatus
    error: str | None
    created_at: datetime


class RunOut(RunSummaryOut):
    summary: str | None
    steps: list[str]
    open_questions: list[str]
    run_metadata: dict[str, Any]
    assumptions: list[AssumptionOut]
    actions: list[ActionOut]


class DecisionOut(ORMModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID
    action_id: uuid.UUID | None
    decision: DecisionType
    rationale: str | None
    reviewer: str
    created_at: datetime


class TaskSummaryOut(ORMModel):
    id: uuid.UUID
    title: str
    review_mode: ReviewMode
    status: TaskStatus
    failure_stage: FailureStage | None
    created_at: datetime
    updated_at: datetime


class TaskOut(TaskSummaryOut):
    description: str
    failure_reason: str | None
    current_run: RunOut | None
    runs: list[RunSummaryOut]
    decisions: list[DecisionOut]
    available_operations: list[str]


class TaskListOut(BaseModel):
    items: list[TaskSummaryOut]
    total: int
    limit: int
    offset: int


class AuditEventOut(ORMModel):
    sequence: int
    event_type: EventType
    actor: Actor
    agent_run_id: uuid.UUID | None
    action_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime
