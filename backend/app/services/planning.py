"""Planning workflow: call the planner, validate its output, apply the review policy.

Planning runs in three phases so a slow planner (e.g. an LLM call) never holds the
task's row lock or an open transaction:

1. ``begin_planning``   (locked)  move the task to PLANNING and commit.
2. planner call         (no lock) produce a raw plan.
3. ``_persist_plan``    (locked)  validate, store, assess, and move the task on.

Moving to PLANNING in phase 1 is what prevents two planning attempts for the same
task from running at once: the second request fails the lifecycle check.
"""

import logging
import time
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.agent.base import Planner, PlannerError, PlannerOutput
from backend.app.agent.schema import AgentPlan, PlanningContext, ReviewerMessage
from backend.app.domain.enums import (
    Actor,
    EventType,
    FailureStage,
    ReviewMode,
    ReviewState,
    RunStatus,
    RunTrigger,
    TaskStatus,
)
from backend.app.errors import ConflictError
from backend.app.models import AgentRun, Assumption, ProposedAction, Task
from backend.app.policy.review import OPEN_QUESTIONS, review_requirement
from backend.app.policy.risk import assess_risk
from backend.app.services.common import change_status, lock_task, record_event
from backend.app.services.execution import execute_current_run
from backend.app.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "side_effect": tool.side_effect,
            "external": tool.external,
            "arguments_schema": tool.args_model.model_json_schema(),
        }
        for tool in TOOL_REGISTRY.values()
    ]


def _build_context(task: Task, trigger: RunTrigger, reviewer_input: str | None) -> PlanningContext:
    messages = [
        ReviewerMessage(trigger=run.trigger, message=run.reviewer_input)
        for run in task.runs
        if run.reviewer_input
    ]
    if reviewer_input:
        messages.append(ReviewerMessage(trigger=trigger, message=reviewer_input))
    return PlanningContext(
        task_title=task.title,
        task_description=task.description,
        attempt_number=len(task.runs) + 1,
        trigger=trigger,
        reviewer_messages=messages,
        available_tools=tool_catalog(),
    )


def begin_planning(
    session: Session, task: Task, trigger: RunTrigger, reviewer_input: str | None, actor: Actor
) -> PlanningContext:
    """Phase 1. The caller holds the task lock and commits afterwards."""
    change_status(session, task, TaskStatus.PLANNING, actor)
    task.failure_stage = None
    task.failure_reason = None
    record_event(session, task, EventType.PLANNING_STARTED, Actor.SYSTEM,
                 {"trigger": trigger, "attempt_number": len(task.runs) + 1})
    return _build_context(task, trigger, reviewer_input)


def _summarize_validation_error(exc: ValidationError) -> str:
    # Field locations and messages only: never echo the raw (untrusted) output.
    parts = [f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}" for err in exc.errors()[:5]]
    more = f" (+{exc.error_count() - 5} more)" if exc.error_count() > 5 else ""
    return "Agent output failed schema validation: " + "; ".join(parts) + more


def _fail_planning(session: Session, task: Task, run: AgentRun, reason: str) -> None:
    run.status = RunStatus.FAILED
    run.error = reason
    record_event(session, task, EventType.PLANNING_FAILED, Actor.SYSTEM, {"error": reason}, run=run)
    task.failure_stage = FailureStage.PLANNING
    task.failure_reason = reason
    change_status(session, task, TaskStatus.FAILED)
    record_event(session, task, EventType.TASK_FAILED, Actor.SYSTEM,
                 {"stage": FailureStage.PLANNING, "reason": reason, "retryable": True}, run=run)


def _persist_plan(
    session: Session,
    task: Task,
    context: PlanningContext,
    planner_name: str,
    output: PlannerOutput | None,
    planner_error: str | None,
    metadata: dict[str, Any],
) -> None:
    reviewer_input = context.reviewer_messages[-1].message if (
        context.reviewer_messages and context.trigger in (RunTrigger.REVISION, RunTrigger.CLARIFICATION)
    ) else None
    run = AgentRun(
        task_id=task.id,
        attempt_number=context.attempt_number,
        trigger=context.trigger,
        reviewer_input=reviewer_input,
        planner=planner_name,
        status=RunStatus.SUCCEEDED,
        steps=[],
        open_questions=[],
        run_metadata=metadata,
    )
    task.runs.append(run)
    session.flush()

    if planner_error is not None or output is None:
        _fail_planning(session, task, run, planner_error or "The planner returned no output")
        return
    try:
        plan = AgentPlan.model_validate(output.raw_plan)
    except ValidationError as exc:
        _fail_planning(session, task, run, _summarize_validation_error(exc))
        return

    run.summary = plan.summary
    run.steps = plan.steps
    run.open_questions = plan.open_questions
    record_event(session, task, EventType.PLANNING_SUCCEEDED, Actor.AGENT,
                 {"actions": len(plan.actions), "assumptions": len(plan.assumptions),
                  "open_questions": len(plan.open_questions)}, run=run)

    basis = {}
    for planned in plan.assumptions:
        assumption = Assumption(
            task_id=task.id, key=planned.key, statement=planned.statement, basis=planned.basis,
            evidence=planned.evidence, consequence_if_wrong=planned.consequence_if_wrong,
        )
        run.assumptions.append(assumption)
        basis[planned.key] = planned.basis
        record_event(session, task, EventType.ASSUMPTION_RECORDED, Actor.AGENT,
                     {"key": planned.key, "basis": planned.basis}, run=run)

    for sequence, planned_action in enumerate(plan.actions, start=1):
        risk = assess_risk(planned_action.tool, planned_action.arguments,
                           planned_action.depends_on_assumptions, basis, planned_action.agent_risk_estimate)
        requirement = review_requirement(task.review_mode, risk)
        action = ProposedAction(
            task_id=task.id,
            sequence=sequence,
            key=planned_action.key,
            description=planned_action.description,
            tool_name=planned_action.tool,
            arguments=planned_action.arguments,
            rationale=planned_action.rationale,
            expected_outcome=planned_action.expected_outcome,
            verification_criteria=[c.model_dump() for c in planned_action.verification],
            depends_on_assumptions=planned_action.depends_on_assumptions,
            agent_risk_estimate=planned_action.agent_risk_estimate,
            risk_level=risk.level,
            risk_factors=list(risk.factors),
            review_required=requirement.required,
            review_reasons=list(requirement.reasons),
            review_state=requirement.initial_state,
        )
        run.actions.append(action)
        session.flush()
        record_event(session, task, EventType.ACTION_PROPOSED, Actor.AGENT,
                     {"key": action.key, "tool": action.tool_name, "agent_risk_estimate": action.agent_risk_estimate},
                     run=run, action=action)
        if requirement.initial_state == ReviewState.BLOCKED:
            record_event(session, task, EventType.ACTION_BLOCKED, Actor.POLICY,
                         {"risk_level": risk.level, "reasons": list(requirement.reasons)}, run=run, action=action)

    advance_after_planning(session, task)


def advance_after_planning(session: Session, task: Task) -> None:
    run = task.current_run
    assert run is not None
    pending = [a for a in run.actions if a.review_state == ReviewState.PENDING]
    needs_clarification = task.review_mode == ReviewMode.STRUCTURED and bool(run.open_questions)
    executable = [a for a in run.actions if a.review_state == ReviewState.NOT_REQUIRED]

    if pending or needs_clarification or not executable:
        reasons = sorted({r for a in pending for r in a.review_reasons})
        if needs_clarification:
            reasons.append(OPEN_QUESTIONS)
        change_status(session, task, TaskStatus.AWAITING_REVIEW)
        record_event(session, task, EventType.REVIEW_REQUESTED, Actor.POLICY,
                     {"pending_actions": [a.key for a in pending], "reasons": reasons,
                      "executable_actions": len(executable) + len(pending)}, run=run)
        return
    change_status(session, task, TaskStatus.RUNNING, reason="no review required")
    execute_current_run(session, task)


def run_planner(
    session: Session, task_id: uuid.UUID, planner: Planner, context: PlanningContext
) -> Task:
    """Phases 2 and 3. Phase 1 must already be committed."""
    started = time.perf_counter()
    output: PlannerOutput | None = None
    error: str | None = None
    try:
        output = planner.plan(context)
    except PlannerError as exc:
        error = f"Planner error: {exc}"
    except Exception:
        logger.exception("Planner %s raised unexpectedly", planner.name)
        error = "The planner failed unexpectedly"
    metadata = {"latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    if output is not None:
        metadata.update(output.metadata)

    session.expire_all()
    task = lock_task(session, task_id)
    if task.status != TaskStatus.PLANNING:
        # Something else changed the task while the planner ran (e.g. manual DB repair).
        session.rollback()
        raise ConflictError("Task left the PLANNING state while the planner was running")
    _persist_plan(session, task, context, planner.name, output, error, metadata)
    session.commit()
    return task


def start_planning(session: Session, task_id: uuid.UUID, planner: Planner) -> Task:
    task = lock_task(session, task_id)
    if task.status != TaskStatus.CREATED:
        raise ConflictError(
            f"Planning can only start from CREATED (current status: {task.status})",
            code="invalid_transition",
        )
    context = begin_planning(session, task, RunTrigger.INITIAL, None, Actor.REVIEWER)
    session.commit()
    return run_planner(session, task_id, planner, context)


def retry_planning(session: Session, task_id: uuid.UUID, planner: Planner) -> Task:
    task = lock_task(session, task_id)
    if task.status != TaskStatus.FAILED or task.failure_stage != FailureStage.PLANNING:
        # Execution failures may have had side effects, so they are never retried blindly.
        raise ConflictError(
            "Only tasks that failed during planning can be retried", code="not_retryable"
        )
    context = begin_planning(session, task, RunTrigger.RETRY, None, Actor.REVIEWER)
    session.commit()
    return run_planner(session, task_id, planner, context)
