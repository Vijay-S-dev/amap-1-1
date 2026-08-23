"""
Task responsibility repository.

Provides database access operations for the task_responsibilities table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class TaskResponsibilitiesRepository:
    """Data access operations for task responsibilities."""

    def get_by_ids(
        self,
        task_id: UUID,
        responsibility_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a task-responsibility link, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, responsibility_id, created_at
                    FROM task_responsibilities
                    WHERE task_id = %s
                      AND responsibility_id = %s
                    """,
                    (task_id, responsibility_id),
                )
                return cursor.fetchone()

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all responsibility links for a task."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, responsibility_id, created_at
                    FROM task_responsibilities
                    WHERE task_id = %s
                    ORDER BY created_at
                    """,
                    (task_id,),
                )
                return cursor.fetchall()

    def list_by_responsibility_id(
        self,
        responsibility_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all task links for a responsibility."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT task_id, responsibility_id, created_at
                    FROM task_responsibilities
                    WHERE responsibility_id = %s
                    ORDER BY created_at
                    """,
                    (responsibility_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        task_id: UUID,
        responsibility_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a task-responsibility link."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO task_responsibilities (
                        task_id,
                        responsibility_id
                    )
                    VALUES (%s, %s)
                    RETURNING task_id, responsibility_id, created_at
                    """,
                    (task_id, responsibility_id),
                )

                task_responsibility = cursor.fetchone()
                connection.commit()

                return task_responsibility

    def delete(
        self,
        task_id: UUID,
        responsibility_id: UUID,
    ) -> bool:
        """Delete a task-responsibility link and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM task_responsibilities
                    WHERE task_id = %s
                      AND responsibility_id = %s
                    """,
                    (task_id, responsibility_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
