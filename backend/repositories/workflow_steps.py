"""
Workflow step repository.

Provides database access operations for the workflow_steps table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkflowStepsRepository:
    """Data access operations for workflow steps."""

    def get_by_id(
        self,
        workflow_step_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a workflow step by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    FROM workflow_steps
                    WHERE id = %s
                    """,
                    (workflow_step_id,),
                )
                return cursor.fetchone()

    def get_by_workflow_and_step_order(
        self,
        workflow_id: UUID,
        step_order: int,
    ) -> dict[str, Any] | None:
        """Return a workflow step by workflow ID and step order."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    FROM workflow_steps
                    WHERE workflow_id = %s
                      AND step_order = %s
                    """,
                    (workflow_id, step_order),
                )
                return cursor.fetchone()

    def list_by_workflow_id(
        self,
        workflow_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all workflow steps for a workflow."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    FROM workflow_steps
                    WHERE workflow_id = %s
                    ORDER BY step_order
                    """,
                    (workflow_id,),
                )
                return cursor.fetchall()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all workflow steps."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    FROM workflow_steps
                    ORDER BY created_at
                    """
                )
                return cursor.fetchall()

    def create(
        self,
        workflow_id: UUID,
        step_order: int,
        name: str,
        description: str | None = None,
        status: str = "active",
        is_safety_critical: bool = False,
        expected_duration_seconds: int = 120,
        required_intent: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a workflow step."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflow_steps (
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                    ),
                )

                workflow_step = cursor.fetchone()
                connection.commit()

                return workflow_step

    def update(
        self,
        workflow_step_id: UUID,
        step_order: int,
        name: str,
        description: str | None,
        status: str,
        is_safety_critical: bool = False,
        expected_duration_seconds: int = 120,
        required_intent: str | None = None,
    ) -> dict[str, Any] | None:
        """Update and return a workflow step, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE workflow_steps
                    SET
                        step_order = %s,
                        name = %s,
                        description = %s,
                        is_safety_critical = %s,
                        expected_duration_seconds = %s,
                        required_intent = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        workflow_id,
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        step_order,
                        name,
                        description,
                        is_safety_critical,
                        expected_duration_seconds,
                        required_intent,
                        status,
                        workflow_step_id,
                    ),
                )

                workflow_step = cursor.fetchone()
                connection.commit()

                return workflow_step

    def delete_by_id(
        self,
        workflow_step_id: UUID,
    ) -> bool:
        """Delete a workflow step and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM workflow_steps
                    WHERE id = %s
                    """,
                    (workflow_step_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
