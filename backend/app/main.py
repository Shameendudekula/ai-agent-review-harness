from fastapi import FastAPI

app = FastAPI(
    title="AI Agent Review Harness API",
    description="Backend API for a human-in-the-loop AI agent review system.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return the API health status."""
    return {
        "status": "ok",
        "service": "ai-agent-review-harness-api",
    }
