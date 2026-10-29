"""Shared fixtures. Tests run against a real PostgreSQL test database.

Set TEST_DATABASE_URL to override the default local database.
"""

import asyncio
import os
from collections.abc import Iterator
from typing import Any

# Configure the environment before any application module reads settings.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://localhost/review_harness_test"
)
os.environ["APP_ENV"] = "test"
os.environ["PLANNER"] = "mock"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.app.db import Base, get_engine, get_session_factory  # noqa: E402
from backend.app.main import app as default_app  # noqa: E402


class Api:
    """Synchronous wrapper around an HTTPX client using the in-process ASGI transport."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    # --- workflow helpers ---

    def create_task(self, description: str, mode: str = "STRUCTURED", title: str = "Test task") -> dict[str, Any]:
        response = self.post("/api/v1/tasks", json={"title": title, "description": description, "review_mode": mode})
        assert response.status_code == 201, response.text
        return response.json()

    def plan(self, task_id: str) -> dict[str, Any]:
        response = self.post(f"/api/v1/tasks/{task_id}/plan")
        assert response.status_code == 200, response.text
        return response.json()

    def create_and_plan(self, description: str, mode: str = "STRUCTURED") -> dict[str, Any]:
        return self.plan(self.create_task(description, mode)["id"])

    def review(self, task_id: str, decision: str, action_id: str | None = None,
               rationale: str | None = None, **extra: Any) -> httpx.Response:
        body: dict[str, Any] = {"decision": decision, **extra}
        if action_id is not None:
            body["action_id"] = action_id
        if rationale is not None:
            body["rationale"] = rationale
        return self.post(f"/api/v1/tasks/{task_id}/reviews", json=body)

    def execute(self, task_id: str) -> dict[str, Any]:
        response = self.post(f"/api/v1/tasks/{task_id}/execute")
        assert response.status_code == 200, response.text
        return response.json()

    def events(self, task_id: str) -> list[dict[str, Any]]:
        response = self.get(f"/api/v1/tasks/{task_id}/events")
        assert response.status_code == 200, response.text
        return response.json()


def action_by_key(task: dict[str, Any], key: str) -> dict[str, Any]:
    return next(a for a in task["current_run"]["actions"] if a["key"] == key)


@pytest.fixture(scope="session")
def migrated_database() -> None:
    # Exercise the real migration path (down then up) rather than create_all().
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_database(request: pytest.FixtureRequest) -> Iterator[None]:
    if "no_db" in request.keywords:
        yield
        return
    request.getfixturevalue("migrated_database")
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with get_engine().begin() as connection:
        # TRUNCATE bypasses the row-level append-only triggers, which is what tests need.
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def api() -> Iterator[Api]:
    yield Api(default_app)
    default_app.dependency_overrides.clear()


@pytest.fixture
def session() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "no_db: test does not need the database")
