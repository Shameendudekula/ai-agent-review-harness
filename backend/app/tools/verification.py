"""Deterministic verification of execution results against declared criteria.

A criterion is ``{"path": "a.b", "operator": "<op>", "expected": <value>}``. The path
is a dotted lookup into the tool's result dictionary. Verification answers "did the
execution achieve what the plan said it would?", which is separate from "did the tool
run without raising?".
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Operator = Literal["equals", "not_equals", "exists", "gte", "lte"]

_MISSING = object()


class VerificationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*$")
    operator: Operator
    expected: Any = None


def _lookup(result: dict[str, Any], path: str) -> Any:
    current: Any = result
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _check(actual: Any, operator: Operator, expected: Any) -> bool:
    if operator == "exists":
        return actual is not _MISSING
    if actual is _MISSING:
        return False
    if operator == "equals":
        return bool(actual == expected)
    if operator == "not_equals":
        return bool(actual != expected)
    numeric = (int, float)
    if not isinstance(actual, numeric) or isinstance(actual, bool) or not isinstance(expected, numeric):
        return False
    return actual >= expected if operator == "gte" else actual <= expected


def verify_result(
    result: dict[str, Any], criteria: list[VerificationCriterion]
) -> tuple[bool, list[dict[str, Any]]]:
    details = []
    for criterion in criteria:
        actual = _lookup(result, criterion.path)
        passed = _check(actual, criterion.operator, criterion.expected)
        details.append(
            {
                "path": criterion.path,
                "operator": criterion.operator,
                "expected": criterion.expected,
                "actual": None if actual is _MISSING else actual,
                "passed": passed,
            }
        )
    return bool(details) and all(d["passed"] for d in details), details
