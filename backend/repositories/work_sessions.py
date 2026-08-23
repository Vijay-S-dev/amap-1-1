"""
Work session repository.

Provides database access operations for the work_sessions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkSessionsRepository:
    """Data access operations for work sessions."""

    def get_by_id(
        self,
        work_session_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a work session by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM work_sessions
                    WHERE id = %s
                    """,
                    (work_session_id,),
                )
                return cursor.fetchone()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all work sessions for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM work_sessions
                    WHERE worker_profile_id = %s
                    ORDER BY started_at
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def list_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        """Return all work sessions with the given status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM work_sessions
                    WHERE status = %s
                    ORDER BY started_at
                    """,
                    (status,),
                )
                return cursor.fetchall()

    def create(
        self,
        worker_profile_id: UUID,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a work session."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO work_sessions (
                        worker_profile_id,
                        status
                    )
                    VALUES (%s, %s)
                    RETURNING
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    """,
                    (
                        worker_profile_id,
                        status,
                    ),
                )

                work_session = cursor.fetchone()
                connection.commit()

                return work_session

    def update_status(
        self,
        work_session_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update a work session status and return it."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE work_sessions
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        work_session_id,
                    ),
                )

                work_session = cursor.fetchone()
                connection.commit()

                return work_session

    def end(
        self,
        work_session_id: UUID,
        status: str = "completed",
    ) -> dict[str, Any] | None:
        """End a work session and return the updated session."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE work_sessions
                    SET
                        status = %s,
                        ended_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        status,
                        started_at,
                        ended_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        work_session_id,
                    ),
                )

                work_session = cursor.fetchone()
                connection.commit()

                return work_session

    def delete_by_id(
        self,
        work_session_id: UUID,
    ) -> bool:
        """Delete a work session and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM work_sessions
                    WHERE id = %s
                    """,
                    (work_session_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
