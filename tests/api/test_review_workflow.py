"""End-to-end workflow tests through the API: planning, review, execution, verification."""

from conftest import action_by_key

CAPACITY = "Estimate how many billing-api instances we need for 50,000 daily active users."
CONFIG = "Validate the billing-api configuration before the release."
CLEANUP = "Clean up old billing events to free storage."
NOTIFY = "Notify the team that the billing-api release is scheduled for Friday."
TIMEOUT = "Increase the billing-api request timeout to 30 seconds."
LEGACY = "Collect the metadata for the legacy-reporting project."
MALFORMED = "Generate a deployment checklist for billing-api (malformed output demo)."


# --------------------------------------------------------------------------- structured mode


def test_low_risk_plan_runs_without_review_and_is_verified(api) -> None:
    task = api.create_and_plan(CAPACITY)
    assert task["status"] == "COMPLETED"
    assert task["decisions"] == []
    calc = action_by_key(task, "calculate")
    assert calc["review_state"] == "NOT_REQUIRED"
    assert calc["authorization_state"] == "GRANTED"
    assert calc["authorization_reason"] == "GRANTED_NO_REVIEW_REQUIRED"
    assert calc["execution_result"]["required_instances"] == 2
    assert calc["verification_state"] == "PASSED"


def test_risky_action_waits_for_review_and_nothing_executes_meanwhile(api) -> None:
    task = api.create_and_plan(CLEANUP)
    assert task["status"] == "AWAITING_REVIEW"
    delete = action_by_key(task, "delete")
    assert delete["risk_level"] == "HIGH"
    assert delete["agent_risk_estimate"] == "MEDIUM"  # agent under-estimated; policy raised it
    assert set(delete["review_reasons"]) == {"IRREVERSIBLE_EFFECT", "UNSUPPORTED_ASSUMPTION", "AGENT_FLAGGED_RISK"}
    assert all(a["execution_state"] == "NOT_STARTED" for a in task["current_run"]["actions"])


def test_approved_reversible_change_executes_and_verifies(api) -> None:
    task = api.create_and_plan(TIMEOUT)
    update = action_by_key(task, "update-timeout")
    response = api.review(task["id"], "APPROVE", update["id"])
    assert response.status_code == 200
    task = response.json()
    # Approval alone does not execute anything.
    assert task["status"] == "AWAITING_REVIEW"
    assert action_by_key(task, "update-timeout")["execution_state"] == "NOT_STARTED"
    assert "execute" in task["available_operations"]
    task = api.execute(task["id"])
    assert task["status"] == "COMPLETED"
    update = action_by_key(task, "update-timeout")
    assert update["review_state"] == "APPROVED"
    assert update["authorization_reason"] == "GRANTED_ACTION_APPROVED"
    assert update["execution_result"]["new_value"] == 30
    assert update["verification_state"] == "PASSED"


def test_rejected_action_never_executes_but_task_continues(api) -> None:
    task = api.create_and_plan(CLEANUP)
    delete = action_by_key(task, "delete")
    task = api.review(task["id"], "REJECT", delete["id"], rationale="Retention is 365 days").json()
    assert task["status"] == "AWAITING_REVIEW"
    task = api.execute(task["id"])
    assert task["status"] == "COMPLETED"
    delete = action_by_key(task, "delete")
    assert delete["review_state"] == "REJECTED"
    assert delete["execution_state"] == "SKIPPED"
    assert delete["execution_result"] is None
    assert action_by_key(task, "read-metadata")["execution_state"] == "SUCCEEDED"


def test_revision_creates_new_run_that_returns_for_review(api) -> None:
    task = api.create_and_plan(CLEANUP)
    old_delete = action_by_key(task, "delete")
    task = api.review(task["id"], "REQUEST_REVISION", old_delete["id"],
                      rationale="Do not delete; archive beyond the retention period").json()

    assert task["status"] == "AWAITING_REVIEW"
    assert [r["attempt_number"] for r in task["runs"]] == [1, 2]
    run = task["current_run"]
    assert run["trigger"] == "REVISION"
    assert run["reviewer_input"].startswith("Do not delete")
    archive = action_by_key(task, "archive")
    assert archive["risk_level"] == "MEDIUM" and archive["review_state"] == "PENDING"

    # A decision about the superseded action is not accepted.
    stale = api.review(task["id"], "APPROVE", old_delete["id"])
    assert stale.status_code == 404
    assert stale.json()["error"]["code"] == "action_not_found"

    api.review(task["id"], "APPROVE", archive["id"])
    task = api.execute(task["id"])
    assert task["status"] == "COMPLETED"
    assert action_by_key(task, "archive")["execution_result"]["restorable"] is True


def test_incorrect_assumption_corrected_by_revision(api) -> None:
    task = api.create_and_plan(CONFIG)
    validate = action_by_key(task, "validate")
    assert "UNSUPPORTED_ASSUMPTION" in validate["review_reasons"]
    assert task["current_run"]["assumptions"][0]["basis"] == "UNSUPPORTED"

    task = api.review(task["id"], "REQUEST_REVISION", rationale="billing-api uses schema v1").json()
    # The corrected plan is read-only and fully supported, so it runs without review.
    assert task["status"] == "COMPLETED"
    assert action_by_key(task, "validate")["execution_result"]["valid"] is True


def test_approving_incorrect_assumption_leads_to_verification_failure(api) -> None:
    task = api.create_and_plan(CONFIG)
    api.review(task["id"], "APPROVE", action_by_key(task, "validate")["id"])
    task = api.execute(task["id"])
    assert task["status"] == "FAILED"
    assert task["failure_stage"] == "VERIFICATION"
    validate = action_by_key(task, "validate")
    assert validate["execution_state"] == "SUCCEEDED"   # the tool ran...
    assert validate["verification_state"] == "FAILED"   # ...but did not achieve the goal
    assert "retry_planning" not in task["available_operations"]


def test_open_questions_require_clarification_before_approval(api) -> None:
    task = api.create_and_plan(NOTIFY)
    notify = action_by_key(task, "notify")
    assert task["current_run"]["open_questions"]
    assert "approve_action" not in task["available_operations"]

    blocked = api.review(task["id"], "APPROVE", notify["id"])
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "open_questions"

    task = api.review(task["id"], "REQUEST_CLARIFICATION", rationale="Post it in #billing-team").json()
    assert task["current_run"]["trigger"] == "CLARIFICATION"
    assert task["current_run"]["open_questions"] == []
    notify = action_by_key(task, "notify")
    assert notify["arguments"]["channel"] == "#billing-team"

    api.review(task["id"], "APPROVE", notify["id"])
    task = api.execute(task["id"])
    assert task["status"] == "COMPLETED"
    assert action_by_key(task, "notify")["execution_result"]["channel"] == "#billing-team"


def test_all_actions_rejected_keeps_task_awaiting_review(api) -> None:
    task = api.create_and_plan(NOTIFY)
    task = api.review(task["id"], "REJECT", action_by_key(task, "notify")["id"], rationale="Not now").json()
    assert task["status"] == "AWAITING_REVIEW"
    assert "request_revision" in task["available_operations"]
    assert "execute" not in task["available_operations"]
    nothing = api.post(f"/api/v1/tasks/{task['id']}/execute")
    assert nothing.status_code == 409
    assert "nothing_to_execute" in nothing.json()["error"]["details"]["blockers"]
    cancelled = api.post(f"/api/v1/tasks/{task['id']}/cancel", json={"reason": "abandoned"})
    assert cancelled.json()["status"] == "CANCELLED"


def test_execution_failure_is_recorded_and_not_retryable(api) -> None:
    task = api.create_and_plan(LEGACY)
    assert task["status"] == "FAILED"
    assert task["failure_stage"] == "EXECUTION"
    action = action_by_key(task, "read-legacy")
    assert action["execution_state"] == "FAILED"
    assert "legacy-reporting" in action["execution_error"]
    response = api.post(f"/api/v1/tasks/{task['id']}/retry-planning")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_retryable"


def test_malformed_agent_output_fails_planning_and_can_be_retried(api) -> None:
    task = api.create_and_plan(MALFORMED)
    assert task["status"] == "FAILED"
    assert task["failure_stage"] == "PLANNING"
    assert task["current_run"]["status"] == "FAILED"
    assert task["current_run"]["actions"] == []
    assert "schema validation" in task["failure_reason"]
    assert task["available_operations"] == ["retry_planning"]

    task = api.post(f"/api/v1/tasks/{task['id']}/retry-planning").json()
    assert task["status"] == "COMPLETED"
    assert task["current_run"]["trigger"] == "RETRY"
    assert task["failure_reason"] is None


# --------------------------------------------------------------------------- baseline mode


def test_baseline_requires_plan_approval_even_for_low_risk(api) -> None:
    task = api.create_and_plan(CAPACITY, mode="BASELINE")
    assert task["status"] == "AWAITING_REVIEW"
    assert task["available_operations"] == ["approve_plan", "reject_plan", "cancel"]
    task = api.review(task["id"], "APPROVE").json()
    assert task["status"] == "COMPLETED"
    assert all(a["authorization_reason"] == "GRANTED_PLAN_APPROVED" for a in task["current_run"]["actions"])


def test_baseline_approval_executes_risky_action(api) -> None:
    # This is the weakness the structured workflow is designed to address.
    task = api.create_and_plan(CLEANUP, mode="BASELINE")
    task = api.review(task["id"], "APPROVE").json()
    assert action_by_key(task, "delete")["execution_state"] == "SUCCEEDED"


def test_baseline_reject_stops_the_task(api) -> None:
    task = api.create_and_plan(CLEANUP, mode="BASELINE")
    task = api.review(task["id"], "REJECT", rationale="Too risky").json()
    assert task["status"] == "CANCELLED"
    assert all(a["execution_state"] == "NOT_STARTED" for a in task["current_run"]["actions"])


def test_baseline_rejects_structured_only_decisions(api) -> None:
    task = api.create_and_plan(CLEANUP, mode="BASELINE")
    revision = api.review(task["id"], "REQUEST_REVISION", rationale="archive instead")
    assert revision.status_code == 409 and revision.json()["error"]["code"] == "decision_not_available"
    per_action = api.review(task["id"], "APPROVE", action_by_key(task, "delete")["id"])
    assert per_action.status_code == 409


# --------------------------------------------------------------------------- invalid operations


def test_review_rules(api) -> None:
    task = api.create_and_plan(CLEANUP)
    delete = action_by_key(task, "delete")
    read = action_by_key(task, "read-metadata")

    no_action = api.review(task["id"], "APPROVE")
    assert no_action.json()["error"]["code"] == "action_required"

    not_required = api.review(task["id"], "APPROVE", read["id"])
    assert not_required.json()["error"]["code"] == "review_not_required"

    missing_rationale = api.review(task["id"], "REJECT", delete["id"])
    assert missing_rationale.status_code == 422

    blank_rationale = api.review(task["id"], "REQUEST_REVISION", rationale="   ")
    assert blank_rationale.status_code == 422


def test_duplicate_decision_is_rejected(api) -> None:
    task = api.create_and_plan(NOTIFY)
    notify = action_by_key(task, "notify")
    first = api.review(task["id"], "REJECT", notify["id"], rationale="no")
    assert first.status_code == 200
    second = api.review(task["id"], "REJECT", notify["id"], rationale="no")
    assert second.status_code == 409 and second.json()["error"]["code"] == "already_decided"
    assert len(api.get(f"/api/v1/tasks/{task['id']}").json()["decisions"]) == 1


def test_operations_in_wrong_state_are_rejected(api) -> None:
    task = api.create_task(CAPACITY)
    early = api.review(task["id"], "APPROVE")
    assert early.status_code == 409 and early.json()["error"]["code"] == "invalid_state"

    api.plan(task["id"])
    replan = api.post(f"/api/v1/tasks/{task['id']}/plan")
    assert replan.status_code == 409 and replan.json()["error"]["code"] == "invalid_transition"
    late = api.review(task["id"], "APPROVE")
    assert late.status_code == 409


def test_execute_requires_complete_review(api) -> None:
    created = api.create_task(TIMEOUT)
    assert api.post(f"/api/v1/tasks/{created['id']}/execute").json()["error"]["code"] == "invalid_state"
    task = api.plan(created["id"])
    early = api.post(f"/api/v1/tasks/{task['id']}/execute")
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "review_incomplete"
    current = api.get(f"/api/v1/tasks/{task['id']}").json()
    assert action_by_key(current, "read-metadata")["execution_state"] == "NOT_STARTED"

    notify = api.create_and_plan(NOTIFY)
    api.review(notify["id"], "REJECT", action_by_key(notify, "notify")["id"], rationale="no")
    blocked = api.post(f"/api/v1/tasks/{notify['id']}/execute").json()["error"]
    assert blocked["code"] == "open_questions"
    assert set(blocked["details"]["blockers"]) == {"open_questions", "nothing_to_execute"}


def test_execute_is_not_repeatable(api) -> None:
    task = api.create_and_plan(TIMEOUT)
    api.review(task["id"], "APPROVE", action_by_key(task, "update-timeout")["id"])
    api.execute(task["id"])
    again = api.post(f"/api/v1/tasks/{task['id']}/execute")
    assert again.status_code == 409
    events = [e["event_type"] for e in api.events(task["id"])]
    assert events.count("EXECUTION_STARTED") == 2  # one per action, once
