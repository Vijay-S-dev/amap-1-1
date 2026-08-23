"""
Workflow assignment repository.

Provides database access operations for the workflow_assignments table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkflowAssignmentsRepository:
    """Data access operations for workflow assignments."""

    def get_by_id(
        self,
        assignment_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a workflow assignment by its ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM workflow_assignments
                    WHERE id = %s
                    """,
                    (assignment_id,),
                )

                return cursor.fetchone()

    def list_by_workflow_id(
        self,
        workflow_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all assignments for a workflow."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM workflow_assignments
                    WHERE workflow_id = %s
                    ORDER BY assigned_at
                    """,
                    (workflow_id,),
                )

                return cursor.fetchall()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all assignments for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    FROM workflow_assignments
                    WHERE worker_profile_id = %s
                    ORDER BY assigned_at
                    """,
                    (worker_profile_id,),
                )

                return cursor.fetchall()

    def create(
        self,
        workflow_id: UUID,
        worker_profile_id: UUID,
        status: str = "assigned",
    ) -> dict[str, Any]:
        """Create and return a workflow assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflow_assignments (
                        workflow_id,
                        worker_profile_id,
                        status
                    )
                    VALUES (%s, %s, %s)
                    RETURNING
                        id,
                        workflow_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    """,
                    (
                        workflow_id,
                        worker_profile_id,
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
    ) -> dict[str, Any] | None:
        """Update assignment status and return the updated assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE workflow_assignments
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        workflow_id,
                        worker_profile_id,
                        status,
                        assigned_at,
                        started_at,
                        completed_at,
                        created_at,
                        updated_at
                    """,
                    (status, assignment_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete_by_id(
        self,
        assignment_id: UUID,
    ) -> bool:
        """Delete a workflow assignment and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM workflow_assignments
                    WHERE id = %s
                    """,
                    (assignment_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
