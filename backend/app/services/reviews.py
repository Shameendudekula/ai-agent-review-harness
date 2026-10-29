"""Human review decisions.

Decisions are validated against the task's review mode and current state, stored as
append-only records, and then drive the workflow:

Structured mode
    APPROVE / REJECT           per action that is pending review.
    REQUEST_REVISION           reviewer feedback; the agent re-plans.
    REQUEST_CLARIFICATION      reviewer answers or asks; the agent re-plans.
    Rejecting an action does not cancel the task. Completing the review does not start
    execution either: the reviewer triggers it explicitly (``execute_reviewed_task``),
    which keeps "approved" and "executed" as separate, visible steps and lets the
    reviewer follow a rejection with a revision request.

Baseline mode
    APPROVE / REJECT for the whole plan. Rejecting stops (cancels) the task.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.agent.base import Planner
from backend.app.domain.enums import (
    Actor,
    DecisionType,
    EventType,
    ReviewMode,
    ReviewState,
    RunTrigger,
    TaskStatus,
)
from backend.app.errors import ConflictError, NotFoundError
from backend.app.models import ProposedAction, ReviewDecision, Task
from backend.app.services.common import change_status, lock_task, record_event
from backend.app.services.execution import execute_current_run
from backend.app.services.planning import begin_planning, run_planner


@dataclass(frozen=True)
class DecisionRequest:
    decision: DecisionType
    action_id: uuid.UUID | None
    rationale: str | None
    reviewer: str


REPLAN_TRIGGERS = {
    DecisionType.REQUEST_REVISION: RunTrigger.REVISION,
    DecisionType.REQUEST_CLARIFICATION: RunTrigger.CLARIFICATION,
}


def _find_action(task: Task, action_id: uuid.UUID) -> ProposedAction:
    run = task.current_run
    assert run is not None
    for action in run.actions:
        if action.id == action_id:
            return action
    raise NotFoundError(
        "Action not found in the current plan", code="action_not_found",
        details={"action_id": str(action_id)},
    )


def _record(session: Session, task: Task, request: DecisionRequest, action: ProposedAction | None) -> ReviewDecision:
    run = task.current_run
    assert run is not None
    decision = ReviewDecision(
        task_id=task.id, agent_run_id=run.id, action_id=action.id if action else None,
        decision=request.decision, rationale=request.rationale, reviewer=request.reviewer,
    )
    task.decisions.append(decision)
    session.flush()
    record_event(
        session, task, EventType.REVIEW_DECISION_RECORDED, Actor.REVIEWER,
        {"decision": request.decision, "scope": "action" if action else "plan",
         "action_key": action.key if action else None, "reviewer": request.reviewer,
         "rationale": request.rationale},
        run=run, action=action,
    )
    return decision


def _start_execution(session: Session, task: Task) -> None:
    change_status(session, task, TaskStatus.RUNNING, Actor.SYSTEM, reason="review complete")
    execute_current_run(session, task)


def _baseline_decision(session: Session, task: Task, request: DecisionRequest) -> None:
    if request.decision not in (DecisionType.APPROVE, DecisionType.REJECT):
        raise ConflictError("Baseline mode only supports approving or stopping the whole plan",
                            code="decision_not_available")
    if request.action_id is not None:
        raise ConflictError("Baseline decisions apply to the whole plan, not to one action",
                            code="decision_not_available")
    run = task.current_run
    assert run is not None
    pending = [a for a in run.actions if a.review_state == ReviewState.PENDING]
    if request.decision == DecisionType.APPROVE and not pending:
        raise ConflictError("The plan has no executable actions to approve", code="nothing_to_approve")

    _record(session, task, request, None)
    new_state = ReviewState.APPROVED if request.decision == DecisionType.APPROVE else ReviewState.REJECTED
    for action in pending:
        action.review_state = new_state
    if request.decision == DecisionType.APPROVE:
        _start_execution(session, task)
    else:
        change_status(session, task, TaskStatus.CANCELLED, Actor.REVIEWER)
        record_event(session, task, EventType.TASK_CANCELLED, Actor.REVIEWER,
                     {"reason": "stopped by reviewer", "rationale": request.rationale})


def _structured_action_decision(session: Session, task: Task, request: DecisionRequest) -> None:
    if request.action_id is None:
        raise ConflictError("Approve and reject decisions must name an action", code="action_required")
    run = task.current_run
    assert run is not None
    action = _find_action(task, request.action_id)
    if action.review_state == ReviewState.BLOCKED:
        raise ConflictError("This action is blocked by policy and cannot be approved or rejected",
                            code="action_blocked", details={"reasons": action.review_reasons})
    if action.review_state == ReviewState.NOT_REQUIRED:
        raise ConflictError("This action does not require review", code="review_not_required")
    if action.review_state != ReviewState.PENDING:
        raise ConflictError(f"This action has already been decided ({action.review_state})",
                            code="already_decided")
    if request.decision == DecisionType.APPROVE and run.open_questions:
        raise ConflictError("Answer the agent's open questions (request clarification) before approving",
                            code="open_questions")

    _record(session, task, request, action)
    action.review_state = (
        ReviewState.APPROVED if request.decision == DecisionType.APPROVE else ReviewState.REJECTED
    )


def review_blockers(task: Task) -> list[str]:
    """Why a structured-mode task cannot be executed yet (empty when it can)."""
    run = task.current_run
    if run is None:
        return ["no_plan"]
    blockers = []
    if any(a.review_state == ReviewState.PENDING for a in run.actions):
        blockers.append("review_incomplete")
    if run.open_questions:
        blockers.append("open_questions")
    if not any(a.review_state in (ReviewState.APPROVED, ReviewState.NOT_REQUIRED) for a in run.actions):
        blockers.append("nothing_to_execute")
    return blockers


def execute_reviewed_task(session: Session, task_id: uuid.UUID) -> Task:
    task = lock_task(session, task_id)
    if task.status != TaskStatus.AWAITING_REVIEW or task.review_mode != ReviewMode.STRUCTURED:
        raise ConflictError("Only structured-mode tasks awaiting review can be executed this way",
                            code="invalid_state")
    blockers = review_blockers(task)
    if blockers:
        raise ConflictError("The plan is not ready to execute", code=blockers[0],
                            details={"blockers": blockers})
    _start_execution(session, task)
    session.commit()
    return task


def submit_decision(
    session: Session, task_id: uuid.UUID, request: DecisionRequest, planner: Planner
) -> Task:
    task = lock_task(session, task_id)
    if task.status != TaskStatus.AWAITING_REVIEW:
        raise ConflictError(f"Task is not awaiting review (current status: {task.status})",
                            code="invalid_state")

    if task.review_mode == ReviewMode.BASELINE:
        _baseline_decision(session, task, request)
        session.commit()
        return task

    if request.decision in (DecisionType.APPROVE, DecisionType.REJECT):
        _structured_action_decision(session, task, request)
        session.commit()
        return task

    # Revision or clarification: supersede the current plan and re-plan.
    action = _find_action(task, request.action_id) if request.action_id else None
    _record(session, task, request, action)
    run = task.current_run
    assert run is not None
    superseded = []
    for candidate in run.actions:
        if candidate.review_state in (ReviewState.PENDING, ReviewState.APPROVED, ReviewState.NOT_REQUIRED):
            candidate.review_state = ReviewState.SUPERSEDED
            superseded.append(candidate.key)
    record_event(session, task, EventType.ACTIONS_SUPERSEDED, Actor.SYSTEM,
                 {"actions": superseded}, run=run)
    trigger = REPLAN_TRIGGERS[request.decision]
    context = begin_planning(session, task, trigger, request.rationale, Actor.REVIEWER)
    session.commit()
    return run_planner(session, task_id, planner, context)
