"""
Application configuration.

Per docs/BACKEND.md §10 (Configuration Rules):
- Configuration comes from environment/configuration sources only.
- No hard-coded secrets.
- Required settings are validated at startup.
- Dev/prod concerns are separated via ENVIRONMENT.

This module intentionally does NOT define any database settings.
Database configuration is owned by docs/DATABASE.md and will be
introduced only after the database foundation phase is approved.
"""

import os
from functools import lru_cache
from typing import List


class Settings:
    """
    Centralized application settings, sourced from environment variables.

    Only foundation-phase settings live here (see BACKEND.md §6/§7).
    Do not add business-specific or database settings to this class.
    """

    def __init__(self) -> None:
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.app_name: str = os.getenv("APP_NAME", "AMAP Backend")
        self.api_version_prefix: str = os.getenv("API_VERSION_PREFIX", "/api/v1")

        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # CORS is environment-driven per BACKEND.md §16.
        # In development, a sane localhost default is provided.
        # In production, CORS_ALLOWED_ORIGINS MUST be explicitly set —
        # unrestricted origins are never allowed permanently in prod.
        raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
        self.cors_allowed_origins: List[str] = (
            [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
            if raw_origins
            else self._default_dev_origins()
        )

        self._validate()

    def _default_dev_origins(self) -> List[str]:
        if self.environment == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return []

    def _validate(self) -> None:
        """
        Validate required settings appropriately (BACKEND.md §10).

        Kept intentionally minimal in the foundation phase — there are no
        secrets, database URLs, or auth settings to validate yet.
        """
        if self.environment == "production" and not self.cors_allowed_origins:
            raise RuntimeError(
                "CORS_ALLOWED_ORIGINS must be explicitly set when "
                "ENVIRONMENT=production. Refusing to start with an "
                "unrestricted or empty CORS configuration in production."
            )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-reading env vars on every call."""
    return Settings()

