"""
Hardened security headers middleware.
Provides standard defense-in-depth HTTP response headers against clickjacking,
MIME-sniffing, and XSS.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


STRICT_CSP = "default-src 'self'"
DEVELOPMENT_SWAGGER_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # FastAPI's development Swagger page uses the pinned jsDelivr
        # Swagger UI bundle and inline bootstrap configuration. Keep the
        # production policy strict and scope the relaxed policy to /docs only.
        is_development_docs = (
            get_settings().environment == "development"
            and request.url.path == "/docs"
        )
        response.headers["Content-Security-Policy"] = (
            DEVELOPMENT_SWAGGER_CSP if is_development_docs else STRICT_CSP
        )
        return response
