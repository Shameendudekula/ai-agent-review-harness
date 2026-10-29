"""Task lifecycle state machine.

The backend is the only component allowed to change a task's status, and it may
only do so along the transitions listed here. Review decisions are stored as
separate records; they influence status but never replace it.
"""

from backend.app.domain.enums import TaskStatus
from backend.app.errors import ConflictError

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.PLANNING, TaskStatus.CANCELLED}),
    TaskStatus.PLANNING: frozenset(
        {TaskStatus.AWAITING_REVIEW, TaskStatus.RUNNING, TaskStatus.FAILED}
    ),
    TaskStatus.AWAITING_REVIEW: frozenset(
        {TaskStatus.RUNNING, TaskStatus.PLANNING, TaskStatus.CANCELLED}
    ),
    TaskStatus.RUNNING: frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED}),
    TaskStatus.COMPLETED: frozenset(),
    # The only exit from FAILED is an explicit planning retry, and the service layer
    # permits it only when the failure happened during planning (no side effects).
    TaskStatus.FAILED: frozenset({TaskStatus.PLANNING}),
    TaskStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED})


class InvalidTransitionError(ConflictError):
    code = "invalid_transition"


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def ensure_transition(current: TaskStatus, target: TaskStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(
            f"Task cannot move from {current} to {target}",
            details={"current_status": current, "requested_status": target},
        )
