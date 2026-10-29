"""Rule-based risk assessment.

Risk is an ordinal level, not a numeric score:

- LOW        read-only, valid arguments, no unsupported assumptions.
- MEDIUM     changes state reversibly, depends on an unsupported assumption, or the
             agent itself flagged elevated risk.
- HIGH       irreversible effect or an effect outside the system (e.g. messaging people).
- FORBIDDEN  the tool is not allowlisted or its arguments are invalid. Never executable.

The level is the maximum over the factors that apply. Tool side effects come from the
trusted registry; the agent's own estimate can raise the level but never lower it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from backend.app.domain.enums import RISK_ORDER, AssumptionBasis, RiskLevel
from backend.app.tools.registry import SideEffect, get_tool


class RiskFactor(StrEnum):
    TOOL_NOT_ALLOWLISTED = "TOOL_NOT_ALLOWLISTED"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    IRREVERSIBLE_EFFECT = "IRREVERSIBLE_EFFECT"
    EXTERNAL_EFFECT = "EXTERNAL_EFFECT"
    STATE_CHANGE = "STATE_CHANGE"
    UNSUPPORTED_ASSUMPTION = "UNSUPPORTED_ASSUMPTION"
    AGENT_FLAGGED_RISK = "AGENT_FLAGGED_RISK"


FACTOR_LEVEL: Mapping[RiskFactor, RiskLevel] = {
    RiskFactor.TOOL_NOT_ALLOWLISTED: RiskLevel.FORBIDDEN,
    RiskFactor.INVALID_ARGUMENTS: RiskLevel.FORBIDDEN,
    RiskFactor.IRREVERSIBLE_EFFECT: RiskLevel.HIGH,
    RiskFactor.EXTERNAL_EFFECT: RiskLevel.HIGH,
    RiskFactor.STATE_CHANGE: RiskLevel.MEDIUM,
    RiskFactor.UNSUPPORTED_ASSUMPTION: RiskLevel.MEDIUM,
    RiskFactor.AGENT_FLAGGED_RISK: RiskLevel.MEDIUM,
}


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    factors: tuple[RiskFactor, ...]


def assess_risk(
    tool_name: str,
    arguments: dict[str, Any],
    depends_on: list[str],
    assumption_basis: Mapping[str, AssumptionBasis],
    agent_risk_estimate: RiskLevel,
) -> RiskAssessment:
    factors: list[RiskFactor] = []
    tool = get_tool(tool_name)
    if tool is None:
        factors.append(RiskFactor.TOOL_NOT_ALLOWLISTED)
    else:
        try:
            tool.args_model.model_validate(arguments)
        except ValidationError:
            factors.append(RiskFactor.INVALID_ARGUMENTS)
        if tool.side_effect == SideEffect.IRREVERSIBLE:
            factors.append(RiskFactor.IRREVERSIBLE_EFFECT)
        elif tool.side_effect == SideEffect.REVERSIBLE_WRITE:
            factors.append(RiskFactor.STATE_CHANGE)
        if tool.external:
            factors.append(RiskFactor.EXTERNAL_EFFECT)

    if any(assumption_basis.get(key) == AssumptionBasis.UNSUPPORTED for key in depends_on):
        factors.append(RiskFactor.UNSUPPORTED_ASSUMPTION)
    if RISK_ORDER[agent_risk_estimate] >= RISK_ORDER[RiskLevel.MEDIUM]:
        factors.append(RiskFactor.AGENT_FLAGGED_RISK)

    level = max((FACTOR_LEVEL[f] for f in factors), key=RISK_ORDER.__getitem__, default=RiskLevel.LOW)
    return RiskAssessment(level=level, factors=tuple(factors))
