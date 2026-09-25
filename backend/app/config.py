"""
Application configuration.

Per docs/BACKEND.md §10 (Configuration Rules):
- Configuration comes from environment/configuration sources only.
- No hard-coded secrets.
- Required settings are validated at startup.
- Dev/prod concerns are separated via ENVIRONMENT.

Database configuration is included because the PostgreSQL schema and
migration foundation are now implemented and approved for backend integration.
"""

import os
from functools import lru_cache
from typing import List
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    """
    Centralized application settings, sourced from environment variables.
    """

    def __init__(self) -> None:
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.app_name: str = os.getenv("APP_NAME", "AMAP Backend")
        self.api_version_prefix: str = os.getenv("API_VERSION_PREFIX", "/api/v1")

        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Database configuration.
        self.database_url: str = os.getenv("DATABASE_URL", "")

        # Authentication / JWT configuration.
        self.jwt_secret_key: str = os.getenv(
            "JWT_SECRET_KEY", "amap-dev-jwt-secret-key-change-in-production-mode"
        )
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        # Development demo users toggle (§ Phase 0 security invariant)
        self.enable_dev_demo_users: bool = os.getenv("ENABLE_DEV_DEMO_USERS", "false").lower() in ("true", "1", "yes")

        # Optional Supabase Integration settings
        self.supabase_url: str = os.getenv("SUPABASE_URL", "")
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        # CORS is environment-driven per BACKEND.md §16.
        # In development, a sane localhost default is provided.
        # In production, CORS_ALLOWED_ORIGINS must be explicitly set.
        raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
        self.cors_allowed_origins: List[str] = (
            [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
            if raw_origins
            else self._default_dev_origins()
        )

        self._validate()

    def _default_dev_origins(self) -> List[str]:
        if self.environment == "development":
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        return []

    def _validate(self) -> None:
        """Validate required application settings."""

        if self.environment == "production":
            if not self.cors_allowed_origins:
                raise RuntimeError(
                    "CORS_ALLOWED_ORIGINS must be explicitly set when "
                    "ENVIRONMENT=production. Refusing to start with an "
                    "unrestricted or empty CORS configuration in production."
                )
            if (
                not self.jwt_secret_key
                or not self.jwt_secret_key.strip()
                or self.jwt_secret_key == "amap-dev-jwt-secret-key-change-in-production-mode"
                or len(self.jwt_secret_key.strip()) < 32
            ):
                raise RuntimeError(
                    "JWT_SECRET_KEY must be explicitly set. JWT_SECRET_KEY must be explicitly configured with a secure key (at least 32 characters) in production."
                )
            if self.enable_dev_demo_users:
                raise RuntimeError(
                    "ENABLE_DEV_DEMO_USERS cannot be enabled when ENVIRONMENT=production."
                )

        if not self.database_url:
            raise RuntimeError("DATABASE_URL must be explicitly set.")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-reading env vars on every call."""
    return Settings()
