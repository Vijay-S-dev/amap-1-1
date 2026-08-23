"""
Workflow step execution repository.

Provides database access operations for the workflow_step_executions table.
Business logic does not belong in this module.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkflowStepExecutionsRepository:
    """Data access operations for workflow step executions."""

    def get_by_id(
        self,
        execution_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a workflow step execution by its ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    FROM workflow_step_executions
                    WHERE id = %s
                    """,
                    (execution_id,),
                )

                return cursor.fetchone()

    def get_by_assignment_and_step(
        self,
        workflow_assignment_id: UUID,
        workflow_step_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an execution by assignment and workflow step, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    FROM workflow_step_executions
                    WHERE workflow_assignment_id = %s
                      AND workflow_step_id = %s
                    """,
                    (
                        workflow_assignment_id,
                        workflow_step_id,
                    ),
                )

                return cursor.fetchone()

    def list_by_workflow_assignment_id(
        self,
        workflow_assignment_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all workflow step executions for an assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    FROM workflow_step_executions
                    WHERE workflow_assignment_id = %s
                    ORDER BY created_at
                    """,
                    (workflow_assignment_id,),
                )

                return cursor.fetchall()

    def list_by_workflow_step_id(
        self,
        workflow_step_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all executions for a workflow step."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    FROM workflow_step_executions
                    WHERE workflow_step_id = %s
                    ORDER BY created_at
                    """,
                    (workflow_step_id,),
                )

                return cursor.fetchall()

    def create(
        self,
        workflow_assignment_id: UUID,
        workflow_step_id: UUID,
        status: str = "pending",
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a workflow step execution."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflow_step_executions (
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    """,
                    (
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                    ),
                )

                execution = cursor.fetchone()
                connection.commit()

                return execution

    def update_status(
        self,
        execution_id: UUID,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        """Update execution status and return the updated execution."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE workflow_step_executions
                    SET
                        status = %s,
                        started_at = %s,
                        completed_at = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        workflow_assignment_id,
                        workflow_step_id,
                        status,
                        started_at,
                        completed_at,
                        notes,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        started_at,
                        completed_at,
                        notes,
                        execution_id,
                    ),
                )

                execution = cursor.fetchone()
                connection.commit()

                return execution

    def delete_by_id(
        self,
        execution_id: UUID,
    ) -> bool:
        """Delete a workflow step execution and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM workflow_step_executions
                    WHERE id = %s
                    """,
                    (execution_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
