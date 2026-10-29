"""Allowlisted mock tools.

This registry is the complete set of operations the system can execute. Each tool:

- declares its side effects in trusted code (the review policy relies on this, not on
  what the agent claims about the action);
- validates its arguments with a strict Pydantic model;
- is deterministic and operates only on the in-memory fixtures below.

No tool touches the real filesystem, network, shell, or any external system. "Write"
tools return a simulated result describing what *would* have changed.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SideEffect(StrEnum):
    NONE = "NONE"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    IRREVERSIBLE = "IRREVERSIBLE"


class ToolExecutionError(Exception):
    """A tool ran but could not complete. The message is safe to show to users."""


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[ToolArgs]
    side_effect: SideEffect
    external: bool
    run: Callable[[Any], dict[str, Any]]


# --------------------------------------------------------------------------------------
# Deterministic fixtures standing in for a real environment.
# --------------------------------------------------------------------------------------

PROJECTS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "billing-api": {
            "name": "billing-api",
            "owner_team": "billing-team",
            "config_schema": "v1",
            "avg_requests_per_user_per_day": 40,
            "instance_capacity_rps": 50,
            "data_retention_days": 365,
        },
        "notification-service": {
            "name": "notification-service",
            "owner_team": "platform-team",
            "config_schema": "v2",
            "avg_requests_per_user_per_day": 12,
            "instance_capacity_rps": 120,
            "data_retention_days": 90,
        },
    }
)

SERVICE_CONFIGS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "billing-api": {"request_timeout_seconds": 15, "max_connections": 200, "log_level": "INFO"},
        "notification-service": {
            "request": {"timeout_seconds": 10},
            "pool": {"max_connections": 50},
            "logging": {"level": "INFO"},
        },
    }
)

CONFIG_SCHEMAS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "v1": frozenset({"request_timeout_seconds", "max_connections", "log_level"}),
        "v2": frozenset({"request", "pool", "logging"}),
    }
)

# Records per dataset, bucketed by age in days (upper bound of each bucket).
DATASETS: Mapping[str, Mapping[int, int]] = MappingProxyType(
    {"billing-events": MappingProxyType({30: 12_000, 90: 30_000, 365: 110_000, 3650: 45_000})}
)

NOTIFICATION_CHANNELS = ("#ops", "#billing-team", "#general")

ProjectKey = Literal["billing-api", "notification-service", "legacy-reporting"]
ServiceName = Literal["billing-api", "notification-service"]
Dataset = Literal["billing-events"]
Channel = Literal["#ops", "#billing-team", "#general"]


def _records_older_than(dataset: str, days: int) -> int:
    return sum(count for bucket, count in DATASETS[dataset].items() if bucket > days)


# --------------------------------------------------------------------------------------
# Tool implementations.
# --------------------------------------------------------------------------------------


class ReadProjectMetadataArgs(ToolArgs):
    # legacy-reporting is a valid identifier with no metadata: it exercises execution failure.
    project_key: ProjectKey


def read_project_metadata(args: ReadProjectMetadataArgs) -> dict[str, Any]:
    metadata = PROJECTS.get(args.project_key)
    if metadata is None:
        raise ToolExecutionError(f"No metadata is available for project '{args.project_key}'")
    return {"project": dict(metadata)}


class CalculateCapacityArgs(ToolArgs):
    daily_active_users: int = Field(ge=1, le=1_000_000_000)
    requests_per_user_per_day: int = Field(ge=1, le=100_000)
    peak_factor: float = Field(ge=1.0, le=20.0)
    instance_capacity_rps: int = Field(ge=1, le=1_000_000)


def calculate_capacity(args: CalculateCapacityArgs) -> dict[str, Any]:
    average_rps = args.daily_active_users * args.requests_per_user_per_day / 86_400
    peak_rps = average_rps * args.peak_factor
    return {
        "average_rps": round(average_rps, 2),
        "peak_rps": round(peak_rps, 2),
        "required_instances": max(1, math.ceil(peak_rps / args.instance_capacity_rps)),
    }


class ValidateConfigArgs(ToolArgs):
    service: ServiceName
    schema_version: Literal["v1", "v2"]


def validate_config(args: ValidateConfigArgs) -> dict[str, Any]:
    config_keys = set(SERVICE_CONFIGS[args.service])
    expected = CONFIG_SCHEMAS[args.schema_version]
    missing = sorted(expected - config_keys)
    unexpected = sorted(config_keys - expected)
    errors = [f"missing key: {k}" for k in missing] + [f"unexpected key: {k}" for k in unexpected]
    return {"service": args.service, "schema_version": args.schema_version, "valid": not errors, "errors": errors}


class UpdateConfigValueArgs(ToolArgs):
    service: Literal["billing-api"]
    key: Literal["request_timeout_seconds", "max_connections", "log_level"]
    value: int | str


def update_config_value(args: UpdateConfigValueArgs) -> dict[str, Any]:
    previous = SERVICE_CONFIGS[args.service][args.key]
    if type(previous) is not type(args.value):
        raise ToolExecutionError(f"'{args.key}' expects a value of type {type(previous).__name__}")
    return {
        "simulated": True,
        "service": args.service,
        "key": args.key,
        "previous_value": previous,
        "new_value": args.value,
        "rollback": {"key": args.key, "value": previous},
    }


class RecordsByAgeArgs(ToolArgs):
    dataset: Dataset
    older_than_days: int = Field(ge=1, le=3650)


def archive_records(args: RecordsByAgeArgs) -> dict[str, Any]:
    return {
        "simulated": True,
        "dataset": args.dataset,
        "archived_count": _records_older_than(args.dataset, args.older_than_days),
        "restorable": True,
    }


def delete_records(args: RecordsByAgeArgs) -> dict[str, Any]:
    return {
        "simulated": True,
        "dataset": args.dataset,
        "deleted_count": _records_older_than(args.dataset, args.older_than_days),
        "restorable": False,
    }


class SendNotificationArgs(ToolArgs):
    channel: Channel
    message: str = Field(min_length=1, max_length=500)


def send_notification(args: SendNotificationArgs) -> dict[str, Any]:
    return {"simulated": True, "delivered": True, "channel": args.channel, "characters": len(args.message)}


_TOOLS = (
    ToolSpec("read_project_metadata", "Read predefined metadata for a project.",
             ReadProjectMetadataArgs, SideEffect.NONE, False, read_project_metadata),
    ToolSpec("calculate_capacity", "Estimate peak load and required service instances.",
             CalculateCapacityArgs, SideEffect.NONE, False, calculate_capacity),
    ToolSpec("validate_config", "Check a service configuration against a schema version.",
             ValidateConfigArgs, SideEffect.NONE, False, validate_config),
    ToolSpec("update_config_value", "Change one configuration value (simulated, reversible).",
             UpdateConfigValueArgs, SideEffect.REVERSIBLE_WRITE, False, update_config_value),
    ToolSpec("archive_records", "Move old records to archive storage (simulated, restorable).",
             RecordsByAgeArgs, SideEffect.REVERSIBLE_WRITE, False, archive_records),
    ToolSpec("delete_records", "Permanently delete old records (simulated, not restorable).",
             RecordsByAgeArgs, SideEffect.IRREVERSIBLE, False, delete_records),
    ToolSpec("send_notification", "Post a message to a team channel (simulated, external).",
             SendNotificationArgs, SideEffect.IRREVERSIBLE, True, send_notification),
)

TOOL_REGISTRY: Mapping[str, ToolSpec] = MappingProxyType({tool.name: tool for tool in _TOOLS})


def get_tool(name: str) -> ToolSpec | None:
    return TOOL_REGISTRY.get(name)
