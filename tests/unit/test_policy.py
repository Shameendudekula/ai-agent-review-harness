"""Unit tests for lifecycle rules, risk assessment, review requirements, and authorization."""

import uuid

import pytest

from backend.app.domain.enums import (
    AssumptionBasis,
    DecisionType,
    ExecutionState,
    ReviewMode,
    ReviewState,
    RiskLevel,
    TaskStatus,
)
from backend.app.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    can_transition,
    ensure_transition,
)
from backend.app.models import AgentRun, Assumption, ProposedAction, ReviewDecision, Task
from backend.app.policy.authorization import AuthorizationReason, authorize
from backend.app.policy.review import BASELINE_PLAN_GATE, LOW_RISK_NO_REVIEW, review_requirement
from backend.app.policy.risk import RiskFactor, assess_risk

pytestmark = pytest.mark.no_db

# --------------------------------------------------------------------------- lifecycle


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.CREATED, TaskStatus.PLANNING),
        (TaskStatus.PLANNING, TaskStatus.AWAITING_REVIEW),
        (TaskStatus.PLANNING, TaskStatus.RUNNING),
        (TaskStatus.AWAITING_REVIEW, TaskStatus.PLANNING),
        (TaskStatus.AWAITING_REVIEW, TaskStatus.RUNNING),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED),
        (TaskStatus.FAILED, TaskStatus.PLANNING),
    ],
)
def test_documented_transitions_are_allowed(current: TaskStatus, target: TaskStatus) -> None:
    ensure_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.CREATED, TaskStatus.RUNNING),
        (TaskStatus.CREATED, TaskStatus.COMPLETED),
        (TaskStatus.AWAITING_REVIEW, TaskStatus.COMPLETED),
        (TaskStatus.RUNNING, TaskStatus.CANCELLED),
        (TaskStatus.COMPLETED, TaskStatus.PLANNING),
        (TaskStatus.CANCELLED, TaskStatus.PLANNING),
        (TaskStatus.FAILED, TaskStatus.RUNNING),
    ],
)
def test_undocumented_transitions_are_rejected(current: TaskStatus, target: TaskStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        ensure_transition(current, target)


def test_terminal_states_have_no_exits() -> None:
    assert ALLOWED_TRANSITIONS[TaskStatus.COMPLETED] == frozenset()
    assert ALLOWED_TRANSITIONS[TaskStatus.CANCELLED] == frozenset()
    assert not any(can_transition(s, TaskStatus.CREATED) for s in TaskStatus)


# --------------------------------------------------------------------------- risk


def _risk(tool: str, args: dict, depends_on=(), basis=None, estimate=RiskLevel.LOW):
    return assess_risk(tool, args, list(depends_on), basis or {}, estimate)


def test_read_only_tool_with_valid_arguments_is_low_risk() -> None:
    risk = _risk("read_project_metadata", {"project_key": "billing-api"})
    assert risk.level == RiskLevel.LOW
    assert risk.factors == ()


def test_unknown_tool_is_forbidden() -> None:
    risk = _risk("run_shell_command", {"command": "ls"})
    assert risk.level == RiskLevel.FORBIDDEN
    assert RiskFactor.TOOL_NOT_ALLOWLISTED in risk.factors


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"project_key": "../../etc/passwd"},
        {"project_key": "billing-api", "extra": 1},
        {"project_key": 5},
    ],
)
def test_invalid_arguments_are_forbidden(args: dict) -> None:
    assert _risk("read_project_metadata", args).level == RiskLevel.FORBIDDEN


def test_irreversible_tool_is_high_risk() -> None:
    risk = _risk("delete_records", {"dataset": "billing-events", "older_than_days": 400})
    assert risk.level == RiskLevel.HIGH
    assert RiskFactor.IRREVERSIBLE_EFFECT in risk.factors


def test_external_tool_is_high_risk() -> None:
    risk = _risk("send_notification", {"channel": "#ops", "message": "hi"})
    assert risk.level == RiskLevel.HIGH
    assert {RiskFactor.EXTERNAL_EFFECT, RiskFactor.IRREVERSIBLE_EFFECT} <= set(risk.factors)


def test_reversible_write_is_medium_risk() -> None:
    risk = _risk("archive_records", {"dataset": "billing-events", "older_than_days": 365})
    assert risk.level == RiskLevel.MEDIUM
    assert risk.factors == (RiskFactor.STATE_CHANGE,)


def test_unsupported_assumption_raises_read_only_action_to_medium() -> None:
    risk = _risk("read_project_metadata", {"project_key": "billing-api"}, ["A1"],
                 {"A1": AssumptionBasis.UNSUPPORTED})
    assert risk.level == RiskLevel.MEDIUM
    assert RiskFactor.UNSUPPORTED_ASSUMPTION in risk.factors


@pytest.mark.parametrize("basis", [AssumptionBasis.STATED, AssumptionBasis.INFERRED])
def test_supported_assumptions_do_not_raise_risk(basis: AssumptionBasis) -> None:
    risk = _risk("read_project_metadata", {"project_key": "billing-api"}, ["A1"], {"A1": basis})
    assert risk.level == RiskLevel.LOW


def test_agent_can_raise_but_not_lower_risk() -> None:
    raised = _risk("read_project_metadata", {"project_key": "billing-api"}, estimate=RiskLevel.HIGH)
    assert raised.level == RiskLevel.MEDIUM
    lowered = _risk("delete_records", {"dataset": "billing-events", "older_than_days": 400},
                    estimate=RiskLevel.LOW)
    assert lowered.level == RiskLevel.HIGH


# --------------------------------------------------------------------------- review requirement


def test_review_requirements_structured_mode() -> None:
    low = review_requirement(ReviewMode.STRUCTURED, _risk("read_project_metadata", {"project_key": "billing-api"}))
    assert (low.required, low.initial_state, low.reasons) == (False, ReviewState.NOT_REQUIRED, (LOW_RISK_NO_REVIEW,))

    high = review_requirement(ReviewMode.STRUCTURED,
                              _risk("delete_records", {"dataset": "billing-events", "older_than_days": 400}))
    assert high.required and high.initial_state == ReviewState.PENDING
    assert RiskFactor.IRREVERSIBLE_EFFECT in high.reasons

    forbidden = review_requirement(ReviewMode.STRUCTURED, _risk("run_shell_command", {}))
    assert not forbidden.required and forbidden.initial_state == ReviewState.BLOCKED


def test_baseline_mode_gates_every_executable_action() -> None:
    low = review_requirement(ReviewMode.BASELINE, _risk("read_project_metadata", {"project_key": "billing-api"}))
    assert low.required and low.reasons == (BASELINE_PLAN_GATE,)
    forbidden = review_requirement(ReviewMode.BASELINE, _risk("run_shell_command", {}))
    assert forbidden.initial_state == ReviewState.BLOCKED


# --------------------------------------------------------------------------- authorization


def _setup(tool: str, args: dict, *, mode=ReviewMode.STRUCTURED, status=TaskStatus.RUNNING,
           review_state=ReviewState.PENDING, open_questions=(), basis=None):
    task = Task(id=uuid.uuid4(), status=status, review_mode=mode)
    run = AgentRun(id=uuid.uuid4(), task_id=task.id, open_questions=list(open_questions))
    run.assumptions = [Assumption(key=k, basis=b) for k, b in (basis or {}).items()]
    action = ProposedAction(
        id=uuid.uuid4(), task_id=task.id, agent_run_id=run.id, tool_name=tool, arguments=args,
        depends_on_assumptions=list((basis or {}).keys()), agent_risk_estimate=RiskLevel.LOW,
        review_state=review_state, execution_state=ExecutionState.NOT_STARTED,
    )
    return task, run, action


def _decision(task, run, action, decision: DecisionType) -> ReviewDecision:
    return ReviewDecision(task_id=task.id, agent_run_id=run.id, action_id=action.id if action else None,
                          decision=decision, reviewer="t")


DELETE = ("delete_records", {"dataset": "billing-events", "older_than_days": 400})


def test_low_risk_action_is_authorized_without_review() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"})
    result = authorize(task, run, action, [])
    assert result.allowed and result.reason == AuthorizationReason.GRANTED_NO_REVIEW_REQUIRED


def test_high_risk_action_requires_an_approval_record() -> None:
    task, run, action = _setup(*DELETE)
    assert authorize(task, run, action, []).reason == AuthorizationReason.DENIED_NO_APPROVAL
    approved = authorize(task, run, action, [_decision(task, run, action, DecisionType.APPROVE)])
    assert approved.allowed and approved.reason == AuthorizationReason.GRANTED_ACTION_APPROVED


def test_forged_review_state_column_does_not_authorize() -> None:
    task, run, action = _setup(*DELETE, review_state=ReviewState.APPROVED)
    action.review_required = False  # also forged
    assert not authorize(task, run, action, []).allowed


def test_rejection_wins_over_approval() -> None:
    task, run, action = _setup(*DELETE)
    decisions = [_decision(task, run, action, DecisionType.APPROVE), _decision(task, run, action, DecisionType.REJECT)]
    assert authorize(task, run, action, decisions).reason == AuthorizationReason.DENIED_REJECTED


def test_approval_from_a_previous_run_does_not_carry_over() -> None:
    task, run, action = _setup(*DELETE)
    old_run = AgentRun(id=uuid.uuid4(), task_id=task.id)
    stale = _decision(task, old_run, action, DecisionType.APPROVE)
    assert authorize(task, run, action, [stale]).reason == AuthorizationReason.DENIED_NO_APPROVAL


def test_approval_for_another_action_does_not_authorize() -> None:
    task, run, action = _setup(*DELETE)
    other = ProposedAction(id=uuid.uuid4())
    assert not authorize(task, run, action, [_decision(task, run, other, DecisionType.APPROVE)]).allowed


@pytest.mark.parametrize(
    ("tool", "args", "reason"),
    [
        ("run_shell_command", {"command": "id"}, AuthorizationReason.DENIED_TOOL_NOT_ALLOWLISTED),
        ("delete_records", {"dataset": "billing-events", "older_than_days": 0},
         AuthorizationReason.DENIED_INVALID_ARGUMENTS),
    ],
)
def test_forbidden_actions_are_denied_even_with_approval(tool, args, reason) -> None:
    task, run, action = _setup(tool, args)
    assert authorize(task, run, action, [_decision(task, run, action, DecisionType.APPROVE)]).reason == reason


def test_task_must_be_running() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"},
                               status=TaskStatus.AWAITING_REVIEW)
    assert authorize(task, run, action, []).reason == AuthorizationReason.DENIED_TASK_NOT_RUNNING


def test_action_from_a_superseded_run_is_denied() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"})
    newer = AgentRun(id=uuid.uuid4(), task_id=task.id, open_questions=[])
    assert authorize(task, newer, action, []).reason == AuthorizationReason.DENIED_NOT_CURRENT_RUN


def test_already_executed_action_is_denied() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"})
    action.execution_state = ExecutionState.SUCCEEDED
    assert authorize(task, run, action, []).reason == AuthorizationReason.DENIED_ALREADY_EXECUTED


def test_open_questions_block_structured_execution() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"},
                               open_questions=["Which channel?"])
    assert authorize(task, run, action, []).reason == AuthorizationReason.DENIED_OPEN_QUESTIONS


def test_baseline_requires_plan_level_approval() -> None:
    task, run, action = _setup("read_project_metadata", {"project_key": "billing-api"}, mode=ReviewMode.BASELINE)
    assert authorize(task, run, action, []).reason == AuthorizationReason.DENIED_NO_APPROVAL
    plan_approval = _decision(task, run, None, DecisionType.APPROVE)
    assert authorize(task, run, action, [plan_approval]).reason == AuthorizationReason.GRANTED_PLAN_APPROVED
