"""
Application entry point.

Per docs/BACKEND.md #6-#9:
- Wires together configuration, middleware foundation, centralized error
  handling, and the /api/v1 versioning structure.
- Keeps route handlers thin — business logic does not belong here.
- Does NOT touch the database. The app must remain independently
  runnable without one (BACKEND.md #17).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.error_handlers import register_error_handlers
from middleware.logging_middleware import RequestLoggingMiddleware
from middleware.rate_limiting import RateLimitingMiddleware
from middleware.request_id import RequestIDMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from routes import api_v1_router
from utils.logger import configure_logging, get_logger


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("amap.startup")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    # Middleware order matters: request ID first so downstream middleware
    # and handlers can rely on request.state.request_id being set.
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitingMiddleware)

    # CORS is environment-driven per BACKEND.md #16 — never hardcoded
    # to unrestricted origins in production (enforced in app/config.py).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(api_v1_router, prefix=settings.api_version_prefix)

    @app.on_event("startup")
    async def preload_vosk_models() -> None:
        """Preload the Vosk speech-recognition models once at startup.

        Runs in a daemon thread so app startup (and imports in tests that do
        not exercise voice) are never blocked. /voice/stream connections and
        /voice/stt-health reflect the resulting state; a missing model is a
        reportable error, never a crash.
        """
        import threading

        from services.vosk_stt_service import get_vosk_registry

        def _preload() -> None:
            try:
                get_vosk_registry().preload()
            except Exception as exc:  # noqa: BLE001 - surfaced via stt-health
                logger.error("Vosk model preload failed: %s", exc)

        threading.Thread(target=_preload, name="vosk-preload", daemon=True).start()

    logger.info(f"{settings.app_name} starting in '{settings.environment}' mode")

    return app


app = create_app()

