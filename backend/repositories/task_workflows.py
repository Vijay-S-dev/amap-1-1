"""
Task workflow repository.

Provides database access operations for the task_workflows table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class TaskWorkflowsRepository:
    """Data access operations for task-workflow links."""

    def get_by_ids(
        self,
        task_id: UUID,
        workflow_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a task-workflow link, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        task_id,
                        workflow_id,
                        created_at
                    FROM task_workflows
                    WHERE task_id = %s
                      AND workflow_id = %s
                    """,
                    (
                        task_id,
                        workflow_id,
                    ),
                )

                return cursor.fetchone()

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all workflow links for a task."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        task_id,
                        workflow_id,
                        created_at
                    FROM task_workflows
                    WHERE task_id = %s
                    ORDER BY created_at
                    """,
                    (task_id,),
                )

                return cursor.fetchall()

    def list_by_workflow_id(
        self,
        workflow_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all task links for a workflow."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        task_id,
                        workflow_id,
                        created_at
                    FROM task_workflows
                    WHERE workflow_id = %s
                    ORDER BY created_at
                    """,
                    (workflow_id,),
                )

                return cursor.fetchall()

    def create(
        self,
        task_id: UUID,
        workflow_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a task-workflow link."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO task_workflows (
                        task_id,
                        workflow_id
                    )
                    VALUES (%s, %s)
                    RETURNING
                        task_id,
                        workflow_id,
                        created_at
                    """,
                    (
                        task_id,
                        workflow_id,
                    ),
                )

                task_workflow = cursor.fetchone()
                connection.commit()

                return task_workflow

    def delete(
        self,
        task_id: UUID,
        workflow_id: UUID,
    ) -> bool:
        """Delete a task-workflow link and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM task_workflows
                    WHERE task_id = %s
                      AND workflow_id = %s
                    """,
                    (
                        task_id,
                        workflow_id,
                    ),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
