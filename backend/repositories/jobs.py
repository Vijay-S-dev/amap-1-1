"""
Job repository.

Provides database access operations for the jobs table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class JobsRepository:
    """Data access operations for jobs."""

    def get_by_id(
        self,
        job_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a job by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a job by organization and name, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM jobs
                    WHERE organization_id = %s
                      AND name = %s
                    """,
                    (organization_id, name),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all jobs for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    FROM jobs
                    WHERE organization_id = %s
                    ORDER BY name
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a job."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        organization_id,
                        name,
                        description,
                        status
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        organization_id,
                        name,
                        description,
                        status,
                    ),
                )

                job = cursor.fetchone()
                connection.commit()

                return job

    def delete_by_id(
        self,
        job_id: UUID,
    ) -> bool:
        """Delete a job and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
