"""Task creation, retrieval, cancellation, and audit history."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.domain.enums import Actor, EventType, ReviewMode, TaskStatus
from backend.app.models import AuditEvent, Task
from backend.app.services.common import change_status, get_task, lock_task, record_event


def create_task(session: Session, title: str, description: str, review_mode: ReviewMode) -> Task:
    task = Task(title=title, description=description, review_mode=review_mode, status=TaskStatus.CREATED)
    session.add(task)
    session.flush()
    record_event(session, task, EventType.TASK_CREATED, Actor.REVIEWER, {"review_mode": review_mode})
    session.commit()
    return task


def list_tasks(
    session: Session, status: TaskStatus | None, limit: int, offset: int
) -> tuple[Sequence[Task], int]:
    query = select(Task)
    count_query = select(func.count()).select_from(Task)
    if status is not None:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    tasks = session.scalars(query.order_by(Task.created_at.desc(), Task.id).limit(limit).offset(offset)).all()
    return tasks, session.scalar(count_query) or 0


def cancel_task(session: Session, task_id: uuid.UUID, reason: str | None) -> Task:
    task = lock_task(session, task_id)
    change_status(session, task, TaskStatus.CANCELLED, Actor.REVIEWER)
    record_event(session, task, EventType.TASK_CANCELLED, Actor.REVIEWER, {"reason": reason})
    session.commit()
    return task


def list_events(session: Session, task_id: uuid.UUID) -> Sequence[AuditEvent]:
    get_task(session, task_id)
    return session.scalars(
        select(AuditEvent).where(AuditEvent.task_id == task_id).order_by(AuditEvent.sequence)
    ).all()
