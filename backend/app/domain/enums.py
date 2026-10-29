"""Enumerations shared by the domain, persistence, and API layers."""

from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewMode(StrEnum):
    """Evaluation condition a task runs under."""

    # Risk-based, per-action review with assumptions, clarification, and revision.
    STRUCTURED = "STRUCTURED"
    # A single approve-or-stop gate for the whole plan.
    BASELINE = "BASELINE"


class FailureStage(StrEnum):
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    AUTHORIZATION = "AUTHORIZATION"


class RunTrigger(StrEnum):
    INITIAL = "INITIAL"
    REVISION = "REVISION"
    CLARIFICATION = "CLARIFICATION"
    RETRY = "RETRY"


class RunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AssumptionBasis(StrEnum):
    # Explicitly stated in the task or confirmed by the reviewer.
    STATED = "STATED"
    # Derived from evidence the agent can cite (e.g. tool output, metadata).
    INFERRED = "INFERRED"
    # The agent has no supporting evidence; treated as a review trigger.
    UNSUPPORTED = "UNSUPPORTED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    # Not executable under any approval: unknown tool or invalid arguments.
    FORBIDDEN = "FORBIDDEN"


RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.FORBIDDEN: 3}


class ReviewState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


class AuthorizationState(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    GRANTED = "GRANTED"
    DENIED = "DENIED"


class ExecutionState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class VerificationState(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class DecisionType(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    REQUEST_REVISION = "REQUEST_REVISION"


class Actor(StrEnum):
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    POLICY = "POLICY"
    REVIEWER = "REVIEWER"


class EventType(StrEnum):
    TASK_CREATED = "TASK_CREATED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"
    PLANNING_STARTED = "PLANNING_STARTED"
    PLANNING_SUCCEEDED = "PLANNING_SUCCEEDED"
    PLANNING_FAILED = "PLANNING_FAILED"
    ASSUMPTION_RECORDED = "ASSUMPTION_RECORDED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_DECISION_RECORDED = "REVIEW_DECISION_RECORDED"
    ACTIONS_SUPERSEDED = "ACTIONS_SUPERSEDED"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_SKIPPED = "EXECUTION_SKIPPED"
    VERIFICATION_PASSED = "VERIFICATION_PASSED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
