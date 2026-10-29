"""Centralized application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Required: there is deliberately no default so a missing value fails at startup.
    database_url: str

    # Comma-separated list of browser origins allowed to call the API.
    cors_allowed_origins: str = "http://localhost:5173"

    # Requests per minute per client for state-changing endpoints. 0 disables the limit.
    rate_limit_per_minute: int = Field(default=60, ge=0)

    planner: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    # Hard cap on tokens per planning call (includes the model's thinking): the cost limit.
    llm_max_output_tokens: int = Field(default=16000, ge=1024, le=32000)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Hosting providers usually hand out postgres:// or postgresql:// URLs;
        # SQLAlchemy needs the driver name to select psycopg 3.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        return value

    @model_validator(mode="after")
    def reject_local_database_in_production(self) -> "Settings":
        # A common deployment mistake is copying the local .env value into the host's settings.
        host = make_url(self.database_url).host
        if self.app_env == "production" and host in (None, "", "localhost", "127.0.0.1", "::1"):
            raise ValueError(
                "DATABASE_URL points to a local database, but APP_ENV is production; "
                "set it to the managed database's connection URL"
            )
        return self

    @model_validator(mode="after")
    def require_llm_key_when_enabled(self) -> "Settings":
        if self.planner == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("ANTHROPIC_API_KEY is required when PLANNER=anthropic")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
