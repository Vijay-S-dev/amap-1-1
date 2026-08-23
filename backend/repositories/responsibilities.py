"""
Responsibility repository.

Provides database access operations for the responsibilities table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class ResponsibilitiesRepository:
    """Data access operations for responsibilities."""

    def get_by_id(
        self,
        responsibility_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a responsibility by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        job_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM responsibilities
                    WHERE id = %s
                    """,
                    (responsibility_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        job_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a responsibility by job and name, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        job_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM responsibilities
                    WHERE job_id = %s
                      AND name = %s
                    """,
                    (job_id, name),
                )
                return cursor.fetchone()

    def list_by_job_id(
        self,
        job_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all responsibilities for a job."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        job_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM responsibilities
                    WHERE job_id = %s
                    ORDER BY name
                    """,
                    (job_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        job_id: UUID,
        name: str,
        description: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a responsibility."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO responsibilities (
                        job_id,
                        name,
                        description,
                        status
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id,
                        job_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        job_id,
                        name,
                        description,
                        status,
                    ),
                )

                responsibility = cursor.fetchone()
                connection.commit()

                return responsibility

    def delete_by_id(
        self,
        responsibility_id: UUID,
    ) -> bool:
        """Delete a responsibility and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM responsibilities
                    WHERE id = %s
                    """,
                    (responsibility_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
