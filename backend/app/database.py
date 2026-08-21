"""
Database connection utilities.

Provides a centralized PostgreSQL connection factory for the backend.
Database connections should be obtained through this module rather than
created directly inside route handlers.
"""

from typing import Generator

import psycopg
from psycopg import Connection

from app.config import get_settings


def get_db_connection() -> Connection:
    """
    Create and return a PostgreSQL database connection.

    The connection URL is read from centralized application settings.
    """
    settings = get_settings()
    return psycopg.connect(settings.database_url)


def get_db() -> Generator[Connection, None, None]:
    """
    FastAPI dependency that provides a database connection.

    The connection is always closed after the request completes.
    """
    connection = get_db_connection()

    try:
        yield connection
    finally:
        connection.close()
