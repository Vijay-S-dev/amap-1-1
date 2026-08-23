"""
Task action repository.

Provides database access operations for the task_actions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class TaskActionsRepository:
    """Data access operations for task actions."""

    def get_by_ids(
        self,
        task_id: UUID,
        action_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a task-action link, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, action_id, created_at
                    FROM task_actions
                    WHERE task_id = %s
                      AND action_id = %s
                    """,
                    (task_id, action_id),
                )
                return cursor.fetchone()

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all action links for a task."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, action_id, created_at
                    FROM task_actions
                    WHERE task_id = %s
                    ORDER BY created_at
                    """,
                    (task_id,),
                )
                return cursor.fetchall()

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all task links for an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, action_id, created_at
                    FROM task_actions
                    WHERE action_id = %s
                    ORDER BY created_at
                    """,
                    (action_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        task_id: UUID,
        action_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a task-action link."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO task_actions (
                        task_id,
                        action_id
                    )
                    VALUES (%s, %s)
                    RETURNING task_id, action_id, created_at
                    """,
                    (task_id, action_id),
                )

                task_action = cursor.fetchone()
                connection.commit()

                return task_action

    def delete(
        self,
        task_id: UUID,
        action_id: UUID,
    ) -> bool:
        """Delete a task-action link and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM task_actions
                    WHERE task_id = %s
                      AND action_id = %s
                    """,
                    (task_id, action_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
