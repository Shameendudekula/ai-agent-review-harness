"""Restricted execution of authorized actions, with verification.

This is the only code path that runs tools. For each action in the current run it:

1. skips actions that were rejected, blocked, or superseded;
2. calls ``authorize`` immediately before execution and records the outcome;
3. runs the allowlisted tool with re-validated arguments;
4. verifies the result against the action's declared criteria.

Execution stops at the first failure: later actions are recorded as skipped and the
task fails. An authorization denial at this point means the workflow reached RUNNING
in an inconsistent state, so the task fails closed rather than continuing.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.domain.enums import (
    Actor,
    AuthorizationState,
    EventType,
    ExecutionState,
    FailureStage,
    ReviewState,
    TaskStatus,
    VerificationState,
)
from backend.app.models import AgentRun, ProposedAction, Task
from backend.app.policy.authorization import authorize
from backend.app.services.common import change_status, record_event
from backend.app.tools.registry import ToolExecutionError, get_tool
from backend.app.tools.verification import VerificationCriterion, verify_result

logger = logging.getLogger(__name__)

MAX_RESULT_BYTES = 20_000

NOT_EXECUTABLE = {ReviewState.REJECTED, ReviewState.BLOCKED, ReviewState.SUPERSEDED}


class _StepFailure(Exception):
    def __init__(self, stage: FailureStage, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _skip(session: Session, task: Task, run: AgentRun, action: ProposedAction, reason: str) -> None:
    action.execution_state = ExecutionState.SKIPPED
    record_event(session, task, EventType.EXECUTION_SKIPPED, Actor.SYSTEM, {"reason": reason},
                 run=run, action=action)


def _run_tool(action: ProposedAction) -> dict[str, Any]:
    tool = get_tool(action.tool_name)
    if tool is None:  # authorization already checked this; kept as a second guard
        raise _StepFailure(FailureStage.AUTHORIZATION, "Tool is not allowlisted")
    try:
        args = tool.args_model.model_validate(action.arguments)
        result = tool.run(args)
    except ToolExecutionError as exc:
        raise _StepFailure(FailureStage.EXECUTION, str(exc)) from exc
    except Exception as exc:
        logger.exception("Tool %s raised unexpectedly", action.tool_name)
        raise _StepFailure(FailureStage.EXECUTION, "The tool failed unexpectedly") from exc
    if not isinstance(result, dict):
        raise _StepFailure(FailureStage.EXECUTION, "The tool returned an unexpected result type")
    try:
        encoded = json.dumps(result)
    except (TypeError, ValueError) as exc:
        raise _StepFailure(FailureStage.EXECUTION, "The tool returned a non-serializable result") from exc
    if len(encoded) > MAX_RESULT_BYTES:
        raise _StepFailure(FailureStage.EXECUTION, "The tool result exceeded the size limit")
    return result


def _execute_one(session: Session, task: Task, run: AgentRun, action: ProposedAction) -> None:
    auth = authorize(task, run, action, task.decisions)
    action.authorization_reason = auth.reason
    if not auth.allowed:
        action.authorization_state = AuthorizationState.DENIED
        record_event(session, task, EventType.AUTHORIZATION_DENIED, Actor.POLICY,
                     {"reason": auth.reason, "tool": action.tool_name}, run=run, action=action)
        action.execution_state = ExecutionState.SKIPPED
        raise _StepFailure(FailureStage.AUTHORIZATION, f"Authorization denied: {auth.reason}")

    action.authorization_state = AuthorizationState.GRANTED
    record_event(session, task, EventType.AUTHORIZATION_GRANTED, Actor.POLICY,
                 {"reason": auth.reason, "tool": action.tool_name}, run=run, action=action)

    record_event(session, task, EventType.EXECUTION_STARTED, Actor.SYSTEM,
                 {"tool": action.tool_name}, run=run, action=action)
    try:
        result = _run_tool(action)
    except _StepFailure as failure:
        action.execution_state = ExecutionState.FAILED
        action.execution_error = failure.reason
        record_event(session, task, EventType.EXECUTION_FAILED, Actor.SYSTEM,
                     {"error": failure.reason}, run=run, action=action)
        raise

    action.execution_state = ExecutionState.SUCCEEDED
    action.execution_result = result
    record_event(session, task, EventType.EXECUTION_SUCCEEDED, Actor.SYSTEM,
                 {"result": result}, run=run, action=action)

    criteria = [VerificationCriterion.model_validate(c) for c in action.verification_criteria]
    passed, details = verify_result(result, criteria)
    action.verification_details = details
    if passed:
        action.verification_state = VerificationState.PASSED
        record_event(session, task, EventType.VERIFICATION_PASSED, Actor.SYSTEM,
                     {"checks": details}, run=run, action=action)
        return
    action.verification_state = VerificationState.FAILED
    record_event(session, task, EventType.VERIFICATION_FAILED, Actor.SYSTEM,
                 {"checks": details}, run=run, action=action)
    raise _StepFailure(FailureStage.VERIFICATION, f"Verification failed for action '{action.key}'")


def execute_current_run(session: Session, task: Task) -> None:
    """Execute the current run of a task that the caller has moved to RUNNING.

    The caller must hold the task row lock and commit afterwards.
    """
    if task.status != TaskStatus.RUNNING:
        raise RuntimeError("execute_current_run requires a RUNNING task")
    run = task.current_run
    assert run is not None

    failure: _StepFailure | None = None
    for action in run.actions:
        if failure is not None:
            _skip(session, task, run, action, "an earlier step failed")
            continue
        if action.review_state in NOT_EXECUTABLE:
            _skip(session, task, run, action, f"review state is {action.review_state}")
            continue
        try:
            _execute_one(session, task, run, action)
        except _StepFailure as exc:
            failure = exc

    if failure is None:
        change_status(session, task, TaskStatus.COMPLETED)
        record_event(session, task, EventType.TASK_COMPLETED, Actor.SYSTEM, run=run)
    else:
        task.failure_stage = failure.stage
        task.failure_reason = failure.reason
        change_status(session, task, TaskStatus.FAILED)
        record_event(session, task, EventType.TASK_FAILED, Actor.SYSTEM,
                     {"stage": failure.stage, "reason": failure.reason}, run=run)
