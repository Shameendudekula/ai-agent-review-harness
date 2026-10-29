"""Health checks and static reference data for clients."""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.agent.mock import SCENARIOS
from backend.app.config import get_settings
from backend.app.db import get_engine
from backend.app.errors import error_body
from backend.app.policy.authorization import AuthorizationReason
from backend.app.policy.review import REASON_EXPLANATIONS
from backend.app.services.planning import tool_catalog

router = APIRouter()

SERVICE_NAME = "ai-agent-review-harness-api"


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness: the process is up. Does not check the database."""
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/health/ready", tags=["health"], response_model=None)
def readiness_check() -> dict[str, str] | JSONResponse:
    """Readiness: the API can reach the database."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content=error_body("database_unavailable", "The database is not reachable"),
        )
    return {"status": "ok", "service": SERVICE_NAME, "database": "ok"}


@router.get("/api/v1/catalog", tags=["catalog"])
def catalog() -> dict[str, Any]:
    """Tools, reason codes, and example tasks, so clients can explain policy decisions."""
    return {
        "planner": get_settings().planner,
        "tools": tool_catalog(),
        "reason_explanations": {str(k): v for k, v in REASON_EXPLANATIONS.items()},
        "authorization_reasons": [r.value for r in AuthorizationReason],
        "example_tasks": [
            {"scenario": s.key, "title": s.title, "description": s.example_description} for s in SCENARIOS
        ],
    }
