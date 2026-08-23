"""
Worker task assignment repository.

Provides database access operations for the worker_task_assignments table.
Business logic does not belong in this module.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkerTaskAssignmentsRepository:
    """Data access operations for worker task assignments."""

    def get_by_id(
        self,
        worker_task_assignment_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker task assignment by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        task_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM worker_task_assignments
                    WHERE id = %s
                    """,
                    (worker_task_assignment_id,),
                )
                return cursor.fetchone()

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all worker task assignments for a task."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        task_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM worker_task_assignments
                    WHERE task_id = %s
                    ORDER BY assigned_at
                    """,
                    (task_id,),
                )
                return cursor.fetchall()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all task assignments for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        task_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM worker_task_assignments
                    WHERE worker_profile_id = %s
                    ORDER BY assigned_at
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        task_id: UUID,
        worker_profile_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a worker task assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_task_assignments (
                        task_id,
                        worker_profile_id
                    )
                    VALUES (%s, %s)
                    RETURNING
                        id,
                        task_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    """,
                    (task_id, worker_profile_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def update_status(
        self,
        worker_task_assignment_id: UUID,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Update assignment status and optional timestamps."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE worker_task_assignments
                    SET
                        status = %s,
                        started_at = %s,
                        completed_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        task_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        started_at,
                        completed_at,
                        worker_task_assignment_id,
                    ),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete_by_id(
        self,
        worker_task_assignment_id: UUID,
    ) -> bool:
        """Delete a worker task assignment and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_task_assignments
                    WHERE id = %s
                    """,
                    (worker_task_assignment_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
