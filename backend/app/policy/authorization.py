"""Backend authorization, evaluated immediately before each tool execution.

A human approval is an input to authorization, not a substitute for it. This function
deliberately ignores the cached ``review_state`` / ``review_required`` columns on the
action and re-derives everything from trusted sources:

- the tool registry (is the tool allowlisted, are the arguments valid);
- a fresh risk assessment and review requirement;
- the append-only ``review_decisions`` records for the current run.

So a forged or corrupted status column, a client-supplied "approved" flag, or text in
the plan claiming pre-approval cannot authorize anything.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from backend.app.domain.enums import (
    DecisionType,
    ExecutionState,
    ReviewMode,
    ReviewState,
    TaskStatus,
)
from backend.app.models import AgentRun, ProposedAction, ReviewDecision, Task
from backend.app.policy.review import review_requirement
from backend.app.policy.risk import assess_risk
from backend.app.tools.registry import get_tool


class AuthorizationReason(StrEnum):
    GRANTED_NO_REVIEW_REQUIRED = "GRANTED_NO_REVIEW_REQUIRED"
    GRANTED_ACTION_APPROVED = "GRANTED_ACTION_APPROVED"
    GRANTED_PLAN_APPROVED = "GRANTED_PLAN_APPROVED"
    DENIED_TASK_NOT_RUNNING = "DENIED_TASK_NOT_RUNNING"
    DENIED_NOT_CURRENT_RUN = "DENIED_NOT_CURRENT_RUN"
    DENIED_ALREADY_EXECUTED = "DENIED_ALREADY_EXECUTED"
    DENIED_TOOL_NOT_ALLOWLISTED = "DENIED_TOOL_NOT_ALLOWLISTED"
    DENIED_INVALID_ARGUMENTS = "DENIED_INVALID_ARGUMENTS"
    DENIED_POLICY_BLOCKED = "DENIED_POLICY_BLOCKED"
    DENIED_OPEN_QUESTIONS = "DENIED_OPEN_QUESTIONS"
    DENIED_REJECTED = "DENIED_REJECTED"
    DENIED_NO_APPROVAL = "DENIED_NO_APPROVAL"


@dataclass(frozen=True)
class AuthorizationResult:
    allowed: bool
    reason: AuthorizationReason


def _deny(reason: AuthorizationReason) -> AuthorizationResult:
    return AuthorizationResult(False, reason)


def authorize(
    task: Task,
    current_run: AgentRun,
    action: ProposedAction,
    decisions: Sequence[ReviewDecision],
) -> AuthorizationResult:
    if task.status != TaskStatus.RUNNING:
        return _deny(AuthorizationReason.DENIED_TASK_NOT_RUNNING)
    if action.agent_run_id != current_run.id or action.task_id != task.id:
        return _deny(AuthorizationReason.DENIED_NOT_CURRENT_RUN)
    if action.execution_state != ExecutionState.NOT_STARTED:
        return _deny(AuthorizationReason.DENIED_ALREADY_EXECUTED)

    tool = get_tool(action.tool_name)
    if tool is None:
        return _deny(AuthorizationReason.DENIED_TOOL_NOT_ALLOWLISTED)
    try:
        tool.args_model.model_validate(action.arguments)
    except ValidationError:
        return _deny(AuthorizationReason.DENIED_INVALID_ARGUMENTS)

    run_decisions = [d for d in decisions if d.agent_run_id == current_run.id]

    if task.review_mode == ReviewMode.BASELINE:
        plan_decisions = [d for d in run_decisions if d.action_id is None]
        if plan_decisions and plan_decisions[-1].decision == DecisionType.APPROVE:
            return AuthorizationResult(True, AuthorizationReason.GRANTED_PLAN_APPROVED)
        return _deny(AuthorizationReason.DENIED_NO_APPROVAL)

    if current_run.open_questions:
        return _deny(AuthorizationReason.DENIED_OPEN_QUESTIONS)

    basis = {a.key: a.basis for a in current_run.assumptions}
    risk = assess_risk(
        action.tool_name, action.arguments, action.depends_on_assumptions, basis,
        action.agent_risk_estimate,
    )
    requirement = review_requirement(task.review_mode, risk)
    # Explicit, so a future FORBIDDEN factor cannot fall through to "no review required".
    if requirement.initial_state == ReviewState.BLOCKED:
        return _deny(AuthorizationReason.DENIED_POLICY_BLOCKED)
    if not requirement.required:
        return AuthorizationResult(True, AuthorizationReason.GRANTED_NO_REVIEW_REQUIRED)

    action_decisions = [d for d in run_decisions if d.action_id == action.id]
    if any(d.decision == DecisionType.REJECT for d in action_decisions):
        return _deny(AuthorizationReason.DENIED_REJECTED)
    if any(d.decision == DecisionType.APPROVE for d in action_decisions):
        return AuthorizationResult(True, AuthorizationReason.GRANTED_ACTION_APPROVED)
    return _deny(AuthorizationReason.DENIED_NO_APPROVAL)
