"""Audit trail: completeness, ordering, association, and content."""

import uuid

from conftest import action_by_key

CLEANUP = "Clean up old billing events to free storage."


def test_full_lifecycle_is_recorded_in_order(api) -> None:
    task = api.create_and_plan(CLEANUP)
    delete = action_by_key(task, "delete")
    task = api.review(task["id"], "REQUEST_REVISION", delete["id"], rationale="archive instead").json()
    api.review(task["id"], "APPROVE", action_by_key(task, "archive")["id"])
    task = api.execute(task["id"])
    assert task["status"] == "COMPLETED"

    events = api.events(task["id"])
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    types = [e["event_type"] for e in events]

    expected_order = [
        "TASK_CREATED", "PLANNING_STARTED", "PLANNING_SUCCEEDED", "ASSUMPTION_RECORDED",
        "ACTION_PROPOSED", "REVIEW_REQUESTED", "REVIEW_DECISION_RECORDED", "ACTIONS_SUPERSEDED",
        "PLANNING_STARTED", "PLANNING_SUCCEEDED", "REVIEW_REQUESTED", "REVIEW_DECISION_RECORDED",
        "AUTHORIZATION_GRANTED", "EXECUTION_STARTED", "EXECUTION_SUCCEEDED", "VERIFICATION_PASSED",
        "TASK_COMPLETED",
    ]
    positions = []
    start = 0
    for event_type in expected_order:
        start = types.index(event_type, start)
        positions.append(start)
    assert positions == sorted(positions)

    decision = next(e for e in events if e["event_type"] == "REVIEW_DECISION_RECORDED")
    assert decision["actor"] == "REVIEWER"
    assert decision["action_id"] == delete["id"]
    assert decision["payload"]["decision"] == "REQUEST_REVISION"
    assert decision["payload"]["rationale"] == "archive instead"

    status_changes = [(e["payload"]["from"], e["payload"]["to"]) for e in events
                      if e["event_type"] == "TASK_STATUS_CHANGED"]
    assert status_changes == [
        ("CREATED", "PLANNING"), ("PLANNING", "AWAITING_REVIEW"), ("AWAITING_REVIEW", "PLANNING"),
        ("PLANNING", "AWAITING_REVIEW"), ("AWAITING_REVIEW", "RUNNING"), ("RUNNING", "COMPLETED"),
    ]


def test_events_are_scoped_to_their_task(api) -> None:
    first = api.create_task("one")
    second = api.create_task("two")
    assert len(api.events(first["id"])) == 1
    assert len(api.events(second["id"])) == 1
    assert api.get(f"/api/v1/tasks/{uuid.uuid4()}/events").status_code == 404


def test_failures_are_recorded_with_stage_and_reason(api) -> None:
    task = api.create_and_plan("Collect the metadata for the legacy-reporting project.")
    events = api.events(task["id"])
    failed = next(e for e in events if e["event_type"] == "EXECUTION_FAILED")
    assert "legacy-reporting" in failed["payload"]["error"]
    final = events[-1]
    assert final["event_type"] == "TASK_FAILED"
    assert final["payload"]["stage"] == "EXECUTION"


def test_decisions_are_preserved_across_revisions(api) -> None:
    task = api.create_and_plan(CLEANUP)
    api.review(task["id"], "REJECT", action_by_key(task, "delete")["id"], rationale="too risky")
    task = api.review(task["id"], "REQUEST_REVISION", rationale="archive instead").json()
    assert [d["decision"] for d in task["decisions"]] == ["REJECT", "REQUEST_REVISION"]
    assert task["decisions"][0]["agent_run_id"] == task["runs"][0]["id"]
