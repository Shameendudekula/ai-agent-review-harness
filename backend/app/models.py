"""SQLAlchemy ORM models.

Entity overview:

- ``tasks``             one row per user task; owns the lifecycle status.
- ``agent_runs``        one row per planning attempt (initial, revision, clarification, retry).
- ``assumptions``       assumptions declared by the agent in a run.
- ``proposed_actions``  tool calls proposed in a run, with policy, authorization,
                        execution and verification state kept in separate columns.
- ``review_decisions``  append-only human decisions.
- ``audit_events``      append-only, per-task ordered event log.

``review_decisions`` and ``audit_events`` are protected against UPDATE and DELETE by
database triggers created in the initial migration.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base
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


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    # Stored as VARCHAR with a CHECK constraint: easier to migrate than native PG enums.
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=40,
        validate_strings=True,
        values_callable=lambda members: [m.value for m in members],
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    review_mode: Mapped[ReviewMode] = mapped_column(enum_column(ReviewMode, "review_mode"))
    status: Mapped[TaskStatus] = mapped_column(enum_column(TaskStatus, "task_status"), index=True)
    failure_stage: Mapped[FailureStage | None] = mapped_column(
        enum_column(FailureStage, "failure_stage")
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="task", order_by="AgentRun.attempt_number"
    )
    decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="task", order_by="ReviewDecision.created_at"
    )

    @property
    def current_run(self) -> "AgentRun | None":
        return self.runs[-1] if self.runs else None


class AgentRun(Base):
    __tablename__ = "agent_runs"
    # The unique index also serves lookups by task_id.
    __table_args__ = (UniqueConstraint("task_id", "attempt_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[RunTrigger] = mapped_column(enum_column(RunTrigger, "run_trigger"))
    # Reviewer feedback or clarification passed to the planner for this attempt.
    reviewer_input: Mapped[str | None] = mapped_column(Text)
    planner: Mapped[str] = mapped_column(String(80))
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus, "run_status"))
    summary: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    open_questions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    # Planner metadata such as latency, model name and token usage. Never secrets.
    run_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_column()

    task: Mapped[Task] = relationship(back_populates="runs")
    assumptions: Mapped[list["Assumption"]] = relationship(
        back_populates="run", order_by="Assumption.key"
    )
    actions: Mapped[list["ProposedAction"]] = relationship(
        back_populates="run", order_by="ProposedAction.sequence"
    )


class Assumption(Base):
    __tablename__ = "assumptions"
    __table_args__ = (UniqueConstraint("agent_run_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"))
    key: Mapped[str] = mapped_column(String(40))
    statement: Mapped[str] = mapped_column(Text)
    basis: Mapped[AssumptionBasis] = mapped_column(enum_column(AssumptionBasis, "assumption_basis"))
    evidence: Mapped[str | None] = mapped_column(Text)
    consequence_if_wrong: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()

    run: Mapped[AgentRun] = relationship(back_populates="assumptions")


class ProposedAction(Base):
    __tablename__ = "proposed_actions"
    __table_args__ = (
        UniqueConstraint("agent_run_id", "sequence"),
        UniqueConstraint("agent_run_id", "key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(40))

    # --- What the agent proposed (untrusted content) ---
    description: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rationale: Mapped[str] = mapped_column(Text)
    expected_outcome: Mapped[str] = mapped_column(Text)
    verification_criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    depends_on_assumptions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    agent_risk_estimate: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel, "agent_risk"))

    # --- Policy assessment (computed by the backend from trusted tool metadata) ---
    risk_level: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel, "risk_level"))
    risk_factors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    review_required: Mapped[bool] = mapped_column(Boolean)
    review_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # --- Workflow state. A display cache: authorization never trusts these columns. ---
    review_state: Mapped[ReviewState] = mapped_column(enum_column(ReviewState, "review_state"))
    authorization_state: Mapped[AuthorizationState] = mapped_column(
        enum_column(AuthorizationState, "authorization_state"),
        default=AuthorizationState.NOT_EVALUATED,
    )
    authorization_reason: Mapped[str | None] = mapped_column(String(60))
    execution_state: Mapped[ExecutionState] = mapped_column(
        enum_column(ExecutionState, "execution_state"), default=ExecutionState.NOT_STARTED
    )
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    execution_error: Mapped[str | None] = mapped_column(Text)
    verification_state: Mapped[VerificationState] = mapped_column(
        enum_column(VerificationState, "verification_state"), default=VerificationState.NOT_RUN
    )
    verification_details: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    run: Mapped[AgentRun] = relationship(back_populates="actions")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    # NULL means the decision applies to the whole plan (run) rather than one action.
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proposed_actions.id"), index=True
    )
    decision: Mapped[DecisionType] = mapped_column(enum_column(DecisionType, "decision_type"))
    rationale: Mapped[str | None] = mapped_column(Text)
    # Self-declared label; the demo has no authentication (see docs/security.md).
    reviewer: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = created_at_column()

    task: Mapped[Task] = relationship(back_populates="decisions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    # The unique index also serves "events for task X in order" queries.
    __table_args__ = (UniqueConstraint("task_id", "sequence"),)

    # Global identity gives a total insertion order; ``sequence`` gives per-task order.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[EventType] = mapped_column(enum_column(EventType, "event_type"))
    actor: Mapped[Actor] = mapped_column(enum_column(Actor, "actor"))
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    action_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposed_actions.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_column()
