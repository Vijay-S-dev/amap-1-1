"""
Worker job assignment repository.

Provides database access operations for the worker_job_assignments table.
Business logic does not belong in this module.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkerJobAssignmentsRepository:
    """Data access operations for worker job assignments."""

    def get_by_id(
        self,
        assignment_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker job assignment by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        job_id,
                        status,
                        assigned_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM worker_job_assignments
                    WHERE id = %s
                    """,
                    (assignment_id,),
                )
                return cursor.fetchone()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all job assignments for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        job_id,
                        status,
                        assigned_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM worker_job_assignments
                    WHERE worker_profile_id = %s
                    ORDER BY assigned_at
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def list_by_job_id(
        self,
        job_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all worker assignments for a job."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        job_id,
                        status,
                        assigned_at,
                        ended_at,
                        created_at,
                        updated_at
                    FROM worker_job_assignments
                    WHERE job_id = %s
                    ORDER BY assigned_at
                    """,
                    (job_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        worker_profile_id: UUID,
        job_id: UUID,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a worker job assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_job_assignments (
                        worker_profile_id,
                        job_id,
                        status
                    )
                    VALUES (%s, %s, %s)
                    RETURNING
                        id,
                        worker_profile_id,
                        job_id,
                        status,
                        assigned_at,
                        ended_at,
                        created_at,
                        updated_at
                    """,
                    (
                        worker_profile_id,
                        job_id,
                        status,
                    ),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def update_status(
        self,
        assignment_id: UUID,
        status: str,
        ended_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Update assignment status and optionally ended_at."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE worker_job_assignments
                    SET
                        status = %s,
                        ended_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        job_id,
                        status,
                        assigned_at,
                        ended_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        ended_at,
                        assignment_id,
                    ),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete_by_id(
        self,
        assignment_id: UUID,
    ) -> bool:
        """Delete a worker job assignment and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_job_assignments
                    WHERE id = %s
                    """,
                    (assignment_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
