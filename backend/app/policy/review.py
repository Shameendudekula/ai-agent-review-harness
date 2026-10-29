"""Review requirements: given a risk assessment, does a human need to decide?

Structured mode reviews per action:
    FORBIDDEN       -> blocked; no human decision can make it executable.
    MEDIUM or HIGH  -> review required; the reasons are the risk factors.
    LOW             -> no review required.
  Open questions in a plan additionally block execution until clarified.

Baseline mode has a single approve-or-stop gate for the whole plan, so every
non-forbidden action is covered by the plan-level decision.
"""

from dataclasses import dataclass

from backend.app.domain.enums import ReviewMode, ReviewState, RiskLevel
from backend.app.policy.risk import RiskAssessment, RiskFactor

BASELINE_PLAN_GATE = "BASELINE_PLAN_GATE"
LOW_RISK_NO_REVIEW = "LOW_RISK_NO_REVIEW"
OPEN_QUESTIONS = "OPEN_QUESTIONS"

REASON_EXPLANATIONS: dict[str, str] = {
    RiskFactor.TOOL_NOT_ALLOWLISTED: "The tool is not on the allowlist. It can never execute.",
    RiskFactor.INVALID_ARGUMENTS: "The arguments do not match the tool's schema. It can never execute.",
    RiskFactor.IRREVERSIBLE_EFFECT: "The effect cannot be undone.",
    RiskFactor.EXTERNAL_EFFECT: "The action affects people or systems outside this application.",
    RiskFactor.STATE_CHANGE: "The action changes state. It is reversible, but still a change.",
    RiskFactor.UNSUPPORTED_ASSUMPTION: "The action depends on an assumption the agent could not support.",
    RiskFactor.AGENT_FLAGGED_RISK: "The agent itself rated this action as risky.",
    BASELINE_PLAN_GATE: "Baseline mode: the whole plan is approved or stopped as one unit.",
    LOW_RISK_NO_REVIEW: "Read-only, valid, and free of unsupported assumptions.",
    OPEN_QUESTIONS: "The agent needs information before the plan can run.",
}


@dataclass(frozen=True)
class ReviewRequirement:
    required: bool
    initial_state: ReviewState
    reasons: tuple[str, ...]


def review_requirement(mode: ReviewMode, risk: RiskAssessment) -> ReviewRequirement:
    if risk.level == RiskLevel.FORBIDDEN:
        return ReviewRequirement(False, ReviewState.BLOCKED, tuple(risk.factors))
    if mode == ReviewMode.BASELINE:
        return ReviewRequirement(True, ReviewState.PENDING, (BASELINE_PLAN_GATE,))
    if risk.level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
        return ReviewRequirement(True, ReviewState.PENDING, tuple(risk.factors))
    return ReviewRequirement(False, ReviewState.NOT_REQUIRED, (LOW_RISK_NO_REVIEW,))
