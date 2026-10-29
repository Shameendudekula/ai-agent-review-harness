import asyncio

import httpx

from backend.app.main import app


def test_health_endpoint_returns_success():
    async def make_request():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(make_request())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-agent-review-harness-api",
    }
