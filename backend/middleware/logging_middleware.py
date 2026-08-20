"""
Request logging middleware.

Logs method, path, status code, and duration for each request.
Per BACKEND.md §14, this must never log request bodies, headers that
may carry secrets/tokens, or other sensitive interaction data —
so only request metadata is captured, never payloads.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logger import get_logger

logger = get_logger("amap.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        request_id = getattr(request.state, "request_id", None)
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms}",
            extra={"request_id": request_id},
        )
        return response

