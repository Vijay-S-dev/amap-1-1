"""
Action repository.

Provides database access operations for the actions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class ActionsRepository:
    """Data access operations for actions."""

    def get_by_id(
        self,
        action_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an action by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        created_at,
                        updated_at
                    FROM actions
                    WHERE id = %s
                    """,
                    (action_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """Return an action by its name, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        created_at,
                        updated_at
                    FROM actions
                    WHERE name = %s
                    """,
                    (name,),
                )
                return cursor.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all actions."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        created_at,
                        updated_at
                    FROM actions
                    ORDER BY created_at
                    """
                )
                return cursor.fetchall()

    def create(
        self,
        name: str,
        display_name: str,
        description: str | None = None,
        category: str = "general",
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO actions (
                        name,
                        display_name,
                        description,
                        category,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        name,
                        display_name,
                        description,
                        category,
                        status,
                    ),
                )

                action = cursor.fetchone()
                connection.commit()

                return action

    def update(
        self,
        action_id: UUID,
        name: str,
        display_name: str,
        description: str | None,
        category: str,
        status: str,
    ) -> dict[str, Any] | None:
        """Update an action and return it, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE actions
                    SET
                        name = %s,
                        display_name = %s,
                        description = %s,
                        category = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        action_id,
                    ),
                )

                action = cursor.fetchone()
                connection.commit()

                return action

    def delete_by_id(
        self,
        action_id: UUID,
    ) -> bool:
        """Delete an action and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM actions
                    WHERE id = %s
                    """,
                    (action_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
