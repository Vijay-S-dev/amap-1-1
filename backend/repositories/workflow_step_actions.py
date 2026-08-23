"""
Workflow step action repository.

Provides database access operations for the workflow_step_actions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkflowStepActionsRepository:
    """Data access operations for workflow step actions."""

    def get_by_ids(
        self,
        workflow_step_id: UUID,
        action_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a workflow-step-action link, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT workflow_step_id, action_id, created_at
                    FROM workflow_step_actions
                    WHERE workflow_step_id = %s
                      AND action_id = %s
                    """,
                    (workflow_step_id, action_id),
                )
                return cursor.fetchone()

    def list_by_workflow_step_id(
        self,
        workflow_step_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all action links for a workflow step."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT workflow_step_id, action_id, created_at
                    FROM workflow_step_actions
                    WHERE workflow_step_id = %s
                    ORDER BY created_at
                    """,
                    (workflow_step_id,),
                )
                return cursor.fetchall()

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all workflow step links for an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT workflow_step_id, action_id, created_at
                    FROM workflow_step_actions
                    WHERE action_id = %s
                    ORDER BY created_at
                    """,
                    (action_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        workflow_step_id: UUID,
        action_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a workflow-step-action link."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflow_step_actions (
                        workflow_step_id,
                        action_id
                    )
                    VALUES (%s, %s)
                    RETURNING workflow_step_id, action_id, created_at
                    """,
                    (workflow_step_id, action_id),
                )

                workflow_step_action = cursor.fetchone()
                connection.commit()

                return workflow_step_action

    def delete(
        self,
        workflow_step_id: UUID,
        action_id: UUID,
    ) -> bool:
        """Delete a workflow-step-action link and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM workflow_step_actions
                    WHERE workflow_step_id = %s
                      AND action_id = %s
                    """,
                    (workflow_step_id, action_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
