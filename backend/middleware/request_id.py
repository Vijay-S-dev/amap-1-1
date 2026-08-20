"""
Request ID middleware.

Per docs/BACKEND.md §15, this is foundational middleware only —
it assigns a request ID for traceability. It does not implement
authentication, organization context, or rate limiting; those are
explicitly out of scope for the foundation phase (BACKEND.md §7).
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming_id if incoming_id else str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

