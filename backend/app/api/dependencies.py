"""FastAPI dependencies that select runtime implementations from configuration."""

from backend.app.agent.base import Planner
from backend.app.agent.mock import MockPlanner
from backend.app.config import get_settings


def get_planner() -> Planner:
    settings = get_settings()
    if settings.planner == "anthropic":
        from backend.app.agent.llm import build_anthropic_planner

        return build_anthropic_planner(settings)
    return MockPlanner()
