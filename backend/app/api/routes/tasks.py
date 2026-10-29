"""Task, review, and audit endpoints. Business logic lives in the service layer."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.agent.base import Planner
from backend.app.api.dependencies import get_planner
from backend.app.api.schemas import (
    AuditEventOut,
    CancelRequest,
    ReviewDecisionCreate,
    TaskCreate,
    TaskListOut,
    TaskOut,
    TaskSummaryOut,
)
from backend.app.db import get_session
from backend.app.domain.enums import FailureStage, ReviewMode, ReviewState, TaskStatus
from backend.app.models import Task
from backend.app.services import planning, reviews, tasks
from backend.app.services.common import get_task

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

SessionDep = Annotated[Session, Depends(get_session)]
PlannerDep = Annotated[Planner, Depends(get_planner)]


def available_operations(task: Task) -> list[str]:
    """What a client may attempt next. Advisory only: every operation is re-validated."""
    ops: list[str] = []
    if task.status == TaskStatus.CREATED:
        ops += ["plan", "cancel"]
    elif task.status == TaskStatus.AWAITING_REVIEW:
        run = task.current_run
        if task.review_mode == ReviewMode.BASELINE:
            ops += ["approve_plan", "reject_plan"]
        else:
            if run and any(a.review_state == ReviewState.PENDING for a in run.actions):
                ops += ["reject_action"] if run.open_questions else ["approve_action", "reject_action"]
            if not reviews.review_blockers(task):
                ops.append("execute")
            ops += ["request_revision", "request_clarification"]
        ops.append("cancel")
    elif task.status == TaskStatus.FAILED and task.failure_stage == FailureStage.PLANNING:
        ops.append("retry_planning")
    return ops


def to_task_out(task: Task) -> TaskOut:
    return TaskOut.model_validate(
        {
            **TaskSummaryOut.model_validate(task).model_dump(),
            "description": task.description,
            "failure_reason": task.failure_reason,
            "current_run": task.current_run,
            "runs": task.runs,
            "decisions": task.decisions,
            "available_operations": available_operations(task),
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskOut)
def create_task(body: TaskCreate, session: SessionDep) -> TaskOut:
    return to_task_out(tasks.create_task(session, body.title, body.description, body.review_mode))


@router.get("", response_model=TaskListOut)
def list_tasks(
    session: SessionDep,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaskListOut:
    items, total = tasks.list_tasks(session, status_filter, limit, offset)
    return TaskListOut(
        items=[TaskSummaryOut.model_validate(t) for t in items], total=total, limit=limit, offset=offset
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task_detail(task_id: uuid.UUID, session: SessionDep) -> TaskOut:
    return to_task_out(get_task(session, task_id))


@router.post("/{task_id}/plan", response_model=TaskOut)
def plan_task(task_id: uuid.UUID, session: SessionDep, planner: PlannerDep) -> TaskOut:
    return to_task_out(planning.start_planning(session, task_id, planner))


@router.post("/{task_id}/retry-planning", response_model=TaskOut)
def retry_planning(task_id: uuid.UUID, session: SessionDep, planner: PlannerDep) -> TaskOut:
    return to_task_out(planning.retry_planning(session, task_id, planner))


@router.post("/{task_id}/reviews", response_model=TaskOut)
def submit_review(
    task_id: uuid.UUID, body: ReviewDecisionCreate, session: SessionDep, planner: PlannerDep
) -> TaskOut:
    request = reviews.DecisionRequest(
        decision=body.decision, action_id=body.action_id, rationale=body.rationale, reviewer=body.reviewer
    )
    return to_task_out(reviews.submit_decision(session, task_id, request, planner))


@router.post("/{task_id}/execute", response_model=TaskOut)
def execute_task(task_id: uuid.UUID, session: SessionDep) -> TaskOut:
    """Start execution after review. Authorization is still checked per action."""
    return to_task_out(reviews.execute_reviewed_task(session, task_id))


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: uuid.UUID, body: CancelRequest, session: SessionDep) -> TaskOut:
    return to_task_out(tasks.cancel_task(session, task_id, body.reason))


@router.get("/{task_id}/events", response_model=list[AuditEventOut])
def list_events(task_id: uuid.UUID, session: SessionDep) -> list[AuditEventOut]:
    return [AuditEventOut.model_validate(e) for e in tasks.list_events(session, task_id)]
