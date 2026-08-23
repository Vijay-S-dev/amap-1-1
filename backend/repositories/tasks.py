"""
Task repository.

Provides database access operations for the tasks table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class TasksRepository:
    """Data access operations for tasks."""

    def get_by_id(
        self,
        task_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a task by its ID, or None if it does not exist."""
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
                    FROM tasks
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                return cursor.fetchone()

    def get_by_organization_and_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a task by organization and name, or None if it does not exist."""
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
                    FROM tasks
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
        """Return all tasks for an organization."""
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
                    FROM tasks
                    WHERE organization_id = %s
                    ORDER BY created_at
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
        """Create and return a task."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO tasks (
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

                task = cursor.fetchone()
                connection.commit()

                return task

    def update(
        self,
        task_id: UUID,
        name: str,
        description: str | None,
        status: str,
    ) -> dict[str, Any] | None:
        """Update a task and return it, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE tasks
                    SET
                        name = %s,
                        description = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
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
                        name,
                        description,
                        status,
                        task_id,
                    ),
                )

                task = cursor.fetchone()
                connection.commit()

                return task

    def delete_by_id(
        self,
        task_id: UUID,
    ) -> bool:
        """Delete a task and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM tasks
                    WHERE id = %s
                    """,
                    (task_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
