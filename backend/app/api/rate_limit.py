"""A small in-memory rate limiter for state-changing requests.

The public demo has no authentication, so this limits how quickly one client can
create tasks or trigger planning. It is per-process: with several API instances each
keeps its own counters, which is acceptable for a single-instance demo deployment.
"""

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.app.errors import error_body

LIMITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WINDOW_SECONDS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, requests_per_minute: int) -> None:
        super().__init__(app)
        self.limit = requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.limit <= 0 or request.method not in LIMITED_METHODS:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client]
            while hits and now - hits[0] > WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = int(WINDOW_SECONDS - (now - hits[0])) + 1
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content=error_body("rate_limited", "Too many requests; try again shortly"),
                )
            hits.append(now)
        return await call_next(request)
