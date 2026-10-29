import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.rate_limit import RateLimitMiddleware
from backend.app.api.routes import meta, tasks
from backend.app.config import Settings, get_settings
from backend.app.errors import register_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    app = FastAPI(
        title="AI Agent Review Harness API",
        description="Backend API for a human-in-the-loop AI agent review system.",
        version="0.1.0",
    )
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    register_error_handlers(app)
    app.include_router(meta.router)
    app.include_router(tasks.router)
    return app


app = create_app()
