"""
Rate limiting middleware for AMAP.
Protects sensitive authentication and API endpoints against brute force attacks.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InMemoryRateLimiter:
    """
    Sliding window in-memory rate limiter.
    """

    def __init__(self, limit: int = 30, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old timestamps
        timestamps = [t for t in self.requests[client_key] if t > window_start]
        self.requests[client_key] = timestamps

        if len(timestamps) >= self.limit:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            return False, max(retry_after, 1)

        self.requests[client_key].append(now)
        return True, 0

    def reset(self) -> None:
        self.requests.clear()


# Global rate limiter instance for auth routes
auth_rate_limiter = InMemoryRateLimiter(limit=20, window_seconds=60)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Apply rate limiting to sensitive authentication endpoints
        if path.startswith("/api/v1/auth"):
            client_ip = request.client.host if request.client else "unknown"
            allowed, retry_after = auth_rate_limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "TOO_MANY_REQUESTS",
                            "message": "Too many requests. Please slow down and try again.",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
