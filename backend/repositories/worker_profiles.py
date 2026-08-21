"""
Worker profile repository.

Provides database access operations for the worker_profiles table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkerProfilesRepository:
    """Data access operations for worker profiles."""

    def get_by_id(
        self,
        worker_profile_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker profile by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, created_at, updated_at
                    FROM worker_profiles
                    WHERE id = %s
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchone()

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker profile by user ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, created_at, updated_at
                    FROM worker_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return cursor.fetchone()

    def create(
        self,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_profiles (user_id)
                    VALUES (%s)
                    RETURNING id, user_id, created_at, updated_at
                    """,
                    (user_id,),
                )

                worker_profile = cursor.fetchone()
                connection.commit()

                return worker_profile

    def delete_by_id(
        self,
        worker_profile_id: UUID,
    ) -> bool:
        """Delete a worker profile and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_profiles
                    WHERE id = %s
                    """,
                    (worker_profile_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
