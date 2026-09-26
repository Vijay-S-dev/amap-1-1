"""
Centralized error handling.

Per docs/BACKEND.md §13:
- Consistent error responses.
- No unnecessary internal stack traces exposed to clients.
- No secrets exposed.
- Appropriate HTTP status codes.
- Structured logging of server-side failures.

Detailed final API error contracts are explicitly out of scope for the
foundation phase (BACKEND.md §13) — this establishes the mechanism only.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.logger import get_logger

logger = get_logger("amap.errors")


def _error_body(message: str, request: Request) -> dict:
    request_id = getattr(request.state, "request_id", None)
    body = {"error": message}
    if request_id:
        body["request_id"] = request_id
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail), request),
            # Preserve headers set on the exception (e.g. WWW-Authenticate for 401,
            # Allow for 405). Dropping them breaks HTTP auth challenges.
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("Request validation failed.", request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        # Full detail goes to server-side structured logs only — never to the client.
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc!r}",
            extra={"request_id": request_id},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("Internal server error.", request),
        )

