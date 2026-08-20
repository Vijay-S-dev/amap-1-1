"""
Structured logging foundation.

Per docs/BACKEND.md §14:
- Must support structured application logging.
- Must NEVER log passwords, secrets, access tokens, database credentials,
  or raw sensitive interaction data.

This is a foundation-phase logger only. Business-specific log fields
(organization context, user identity, etc.) will be added once those
concepts exist per approved later phases.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON for easy ingestion later."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request_id if the middleware set it on the record.
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging once, at application startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

