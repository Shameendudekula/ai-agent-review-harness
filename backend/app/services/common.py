"""Helpers shared by the services: row locking, status changes, and audit events."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.domain.enums import Actor, EventType, TaskStatus
from backend.app.domain.lifecycle import ensure_transition
from backend.app.errors import NotFoundError
from backend.app.models import AgentRun, AuditEvent, ProposedAction, Task


def get_task(session: Session, task_id: uuid.UUID) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id} was not found")
    return task


def lock_task(session: Session, task_id: uuid.UUID) -> Task:
    """Load a task with a row lock held until the transaction ends.

    Every state-changing operation takes this lock first, so concurrent requests for
    the same task (for example a double-clicked approval) are applied one at a time
    and the second one sees the first one's result.
    """
    task = session.get(Task, task_id, with_for_update=True, populate_existing=True)
    if task is None:
        raise NotFoundError(f"Task {task_id} was not found")
    return task


def record_event(
    session: Session,
    task: Task,
    event_type: EventType,
    actor: Actor,
    payload: dict[str, Any] | None = None,
    *,
    run: AgentRun | None = None,
    action: ProposedAction | None = None,
) -> AuditEvent:
    # Safe because callers hold the task row lock: no concurrent writer for this task.
    session.flush()
    last = session.scalar(
        select(func.coalesce(func.max(AuditEvent.sequence), 0)).where(AuditEvent.task_id == task.id)
    )
    event = AuditEvent(
        task_id=task.id,
        sequence=(last or 0) + 1,
        event_type=event_type,
        actor=actor,
        agent_run_id=run.id if run else None,
        action_id=action.id if action else None,
        payload=payload or {},
    )
    session.add(event)
    session.flush()
    return event


def change_status(
    session: Session, task: Task, target: TaskStatus, actor: Actor = Actor.SYSTEM, **payload: Any
) -> None:
    ensure_transition(task.status, target)
    previous = task.status
    task.status = target
    record_event(
        session, task, EventType.TASK_STATUS_CHANGED, actor,
        {"from": previous, "to": target, **payload},
    )
