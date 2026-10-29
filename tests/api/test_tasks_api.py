"""Task API: creation, retrieval, listing, validation, errors, and persistence."""

import uuid

from sqlalchemy import select

from backend.app.models import Task


def test_create_task_returns_created_task(api) -> None:
    response = api.post("/api/v1/tasks", json={"title": "  Capacity  ", "description": "Estimate capacity"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Capacity"
    assert body["status"] == "CREATED"
    assert body["review_mode"] == "STRUCTURED"
    assert body["current_run"] is None
    assert body["available_operations"] == ["plan", "cancel"]
    uuid.UUID(body["id"])


def test_created_task_is_persisted(api, session) -> None:
    task = api.create_task("Estimate capacity", mode="BASELINE")
    stored = session.scalars(select(Task)).one()
    assert str(stored.id) == task["id"]
    assert stored.review_mode == "BASELINE"


def test_get_task_by_id(api) -> None:
    task = api.create_task("Estimate capacity")
    response = api.get(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == task["id"]


def test_list_tasks_newest_first_with_pagination_and_filter(api) -> None:
    ids = [api.create_task(f"Task {i}")["id"] for i in range(3)]
    api.post(f"/api/v1/tasks/{ids[0]}/cancel", json={})

    page = api.get("/api/v1/tasks", params={"limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["id"] == ids[2]

    cancelled = api.get("/api/v1/tasks", params={"status": "CANCELLED"}).json()
    assert [t["id"] for t in cancelled["items"]] == [ids[0]]


def test_missing_task_returns_404(api) -> None:
    response = api.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_malformed_task_id_returns_422(api) -> None:
    response = api.get("/api/v1/tasks/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_invalid_create_requests_are_rejected(api) -> None:
    cases = [
        {},
        {"title": "x"},
        {"title": "", "description": "d"},
        {"title": "   ", "description": "d"},
        {"title": "x" * 201, "description": "d"},
        {"title": "t", "description": "d" * 5001},
        {"title": "t", "description": "d", "review_mode": "AUTONOMOUS"},
        {"title": "t", "description": "d", "status": "COMPLETED"},
        {"title": 5, "description": "d"},
    ]
    for body in cases:
        response = api.post("/api/v1/tasks", json=body)
        assert response.status_code == 422, body
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert isinstance(error["details"], list)


def test_list_rejects_invalid_query_parameters(api) -> None:
    assert api.get("/api/v1/tasks", params={"limit": 0}).status_code == 422
    assert api.get("/api/v1/tasks", params={"limit": 101}).status_code == 422
    assert api.get("/api/v1/tasks", params={"status": "DONE"}).status_code == 422


def test_unknown_route_and_method_use_error_format(api) -> None:
    assert api.get("/api/v1/nothing").json()["error"]["code"] == "not_found"
    response = api.request("DELETE", "/api/v1/tasks")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_cancel_created_task_and_reject_cancel_of_terminal_task(api) -> None:
    task = api.create_task("Something")
    response = api.post(f"/api/v1/tasks/{task['id']}/cancel", json={"reason": "not needed"})
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"

    again = api.post(f"/api/v1/tasks/{task['id']}/cancel", json={})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "invalid_transition"


def test_catalog_lists_tools_reasons_and_examples(api) -> None:
    body = api.get("/api/v1/catalog").json()
    assert body["planner"] == "mock"
    assert {t["name"] for t in body["tools"]} >= {"read_project_metadata", "delete_records"}
    assert "IRREVERSIBLE_EFFECT" in body["reason_explanations"]
    assert len(body["example_tasks"]) == 8


def test_readiness_checks_database(api) -> None:
    response = api.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
