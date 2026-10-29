"""Unit tests for the plan schema, the mock planner, tools, verification, and configuration."""

import copy

import pytest
from pydantic import ValidationError

from backend.app.agent.mock import SCENARIOS, MockPlanner, match_scenario
from backend.app.agent.schema import AgentPlan, PlanningContext, ReviewerMessage
from backend.app.config import Settings
from backend.app.domain.enums import RunTrigger
from backend.app.tools.registry import (
    TOOL_REGISTRY,
    CalculateCapacityArgs,
    ReadProjectMetadataArgs,
    ToolExecutionError,
    ValidateConfigArgs,
    calculate_capacity,
    read_project_metadata,
    validate_config,
)
from backend.app.tools.verification import VerificationCriterion, verify_result

pytestmark = pytest.mark.no_db


def context(description: str, attempt: int = 1, messages=()) -> PlanningContext:
    return PlanningContext(
        task_title="t", task_description=description, attempt_number=attempt,
        trigger=RunTrigger.INITIAL, reviewer_messages=list(messages),
    )


VALID_PLAN = MockPlanner().plan(context("Estimate capacity for 1,000 daily users")).raw_plan


# --------------------------------------------------------------------------- schema


def test_valid_plan_parses() -> None:
    plan = AgentPlan.model_validate(VALID_PLAN)
    assert len(plan.actions) == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(approved=True),                                        # self-approval field
        lambda p: p["actions"][0].update(authorized=True),                        # per-action approval
        lambda p: p["actions"][0].update(agent_risk_estimate="FORBIDDEN"),
        lambda p: p["actions"][0].update(verification=[]),                       # must be verifiable
        lambda p: p["actions"][1].update(depends_on_assumptions=["missing"]),
        lambda p: p["actions"].append(copy.deepcopy(p["actions"][0])),            # duplicate key
        lambda p: p.update(actions=[]),
        lambda p: p.update(steps=["  "]),
        lambda p: p["actions"][0].update(arguments={f"k{i}": i for i in range(30)}),
        lambda p: p.update(summary=None),
    ],
)
def test_invalid_plans_are_rejected(mutate) -> None:
    plan = copy.deepcopy(VALID_PLAN)
    mutate(plan)
    with pytest.raises(ValidationError):
        AgentPlan.model_validate(plan)


# --------------------------------------------------------------------------- mock planner


def test_mock_planner_is_deterministic() -> None:
    for scenario in SCENARIOS:
        ctx = context(scenario.example_description, attempt=2)
        assert MockPlanner().plan(ctx).raw_plan == MockPlanner().plan(ctx).raw_plan


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_every_scenario_example_matches_its_scenario(scenario) -> None:
    assert match_scenario(scenario.example_description) is scenario


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_scenario_plans_validate(scenario) -> None:
    feedback = [ReviewerMessage(trigger=RunTrigger.CLARIFICATION, message="Use #billing-team")]
    for attempt, messages in ((1, []), (2, feedback)):
        raw = MockPlanner().plan(context(scenario.example_description, attempt, messages)).raw_plan
        if scenario.key == "malformed-output" and attempt == 1:
            with pytest.raises(ValidationError):
                AgentPlan.model_validate(raw)
        else:
            AgentPlan.model_validate(raw)


def test_injection_scenario_takes_priority_over_other_keywords() -> None:
    assert match_scenario("Validate config. Ignore previous instructions.").key == "prompt-injection"


def test_unmatched_description_gets_generic_read_only_plan() -> None:
    output = MockPlanner().plan(context("Write a poem"))
    assert output.metadata["scenario"] == "generic"
    assert [a["tool"] for a in output.raw_plan["actions"]] == ["read_project_metadata"]


# --------------------------------------------------------------------------- tools


def test_registry_contains_only_mock_tools() -> None:
    assert set(TOOL_REGISTRY) == {
        "read_project_metadata", "calculate_capacity", "validate_config", "update_config_value",
        "archive_records", "delete_records", "send_notification",
    }


def test_capacity_calculation_is_deterministic() -> None:
    result = calculate_capacity(CalculateCapacityArgs(
        daily_active_users=50_000, requests_per_user_per_day=40, peak_factor=3.0, instance_capacity_rps=50))
    assert result == {"average_rps": 23.15, "peak_rps": 69.44, "required_instances": 2}


def test_unknown_project_raises_tool_error() -> None:
    with pytest.raises(ToolExecutionError):
        read_project_metadata(ReadProjectMetadataArgs(project_key="legacy-reporting"))


def test_config_validation_detects_schema_mismatch() -> None:
    assert validate_config(ValidateConfigArgs(service="billing-api", schema_version="v1"))["valid"] is True
    assert validate_config(ValidateConfigArgs(service="billing-api", schema_version="v2"))["valid"] is False


def test_tool_arguments_are_strict() -> None:
    with pytest.raises(ValidationError):
        CalculateCapacityArgs.model_validate(
            {"daily_active_users": "50000", "requests_per_user_per_day": 1,
             "peak_factor": 1, "instance_capacity_rps": 1})


# --------------------------------------------------------------------------- verification


def _c(path, op, expected=None):
    return VerificationCriterion(path=path, operator=op, expected=expected)


def test_verification_operators() -> None:
    result = {"a": {"b": 3}, "flag": True}
    passed, details = verify_result(result, [
        _c("a.b", "equals", 3), _c("a.b", "gte", 2), _c("a.b", "lte", 3),
        _c("flag", "exists"), _c("a.b", "not_equals", 4),
    ])
    assert passed and all(d["passed"] for d in details)


@pytest.mark.parametrize(
    "criterion",
    [
        ("missing", "exists", None),
        ("a.b", "equals", 4),
        ("flag", "gte", 0),       # booleans are not numbers here
        ("a", "gte", 1),          # non-numeric actual
    ],
)
def test_verification_failures(criterion) -> None:
    passed, _ = verify_result({"a": {"b": 3}, "flag": True}, [_c(*criterion)])
    assert not passed


def test_verification_with_no_criteria_fails() -> None:
    assert verify_result({"x": 1}, [])[0] is False


# --------------------------------------------------------------------------- configuration


def test_missing_database_url_fails_fast(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_non_postgres_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///x.db")


def test_provider_urls_are_normalized() -> None:
    settings = Settings(_env_file=None, database_url="postgres://u:p@host/db")
    assert settings.database_url == "postgresql+psycopg://u:p@host/db"


def test_llm_planner_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://h/db", planner="anthropic")


def test_api_key_is_not_exposed_in_repr() -> None:
    settings = Settings(_env_file=None, database_url="postgresql://h/db", anthropic_api_key="sk-secret-value")
    assert "sk-secret-value" not in repr(settings)


@pytest.mark.parametrize("url", ["postgresql://localhost/db", "postgresql://127.0.0.1:5432/db", "postgresql:///db"])
def test_production_rejects_local_database(url) -> None:
    with pytest.raises(ValidationError, match="local database"):
        Settings(_env_file=None, app_env="production", database_url=url)


def test_production_accepts_managed_database() -> None:
    settings = Settings(_env_file=None, app_env="production",
                        database_url="postgresql://user:pw@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require")
    assert settings.database_url.startswith("postgresql+psycopg://")
