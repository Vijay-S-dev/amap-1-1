"""
Action requirement repository.

Provides database access operations for the action_requirements table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class ActionRequirementsRepository:
    """Data access operations for action requirements."""

    def get_by_id(
        self,
        action_requirement_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an action requirement by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status,
                        created_at,
                        updated_at
                    FROM action_requirements
                    WHERE id = %s
                    """,
                    (action_requirement_id,),
                )
                return cursor.fetchone()

    def get_by_action_id_and_name(
        self,
        action_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return an action requirement by action ID and name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status,
                        created_at,
                        updated_at
                    FROM action_requirements
                    WHERE action_id = %s
                      AND name = %s
                    """,
                    (action_id, name),
                )
                return cursor.fetchone()

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all requirements for an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status,
                        created_at,
                        updated_at
                    FROM action_requirements
                    WHERE action_id = %s
                    ORDER BY created_at
                    """,
                    (action_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        action_id: UUID,
        name: str,
        description: str | None = None,
        requirement_type: str = "validation",
        requirement_data: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return an action requirement."""
        if requirement_data is None:
            requirement_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO action_requirements (
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        action_id,
                        name,
                        description,
                        requirement_type,
                        Jsonb(requirement_data),
                        status,
                    ),
                )

                action_requirement = cursor.fetchone()
                connection.commit()

                return action_requirement

    def update(
        self,
        action_requirement_id: UUID,
        name: str,
        description: str | None,
        requirement_type: str,
        requirement_data: dict[str, Any],
        status: str,
    ) -> dict[str, Any] | None:
        """Update an action requirement and return it."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE action_requirements
                    SET
                        name = %s,
                        description = %s,
                        requirement_type = %s,
                        requirement_data = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        action_id,
                        name,
                        description,
                        requirement_type,
                        requirement_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        name,
                        description,
                        requirement_type,
                        Jsonb(requirement_data),
                        status,
                        action_requirement_id,
                    ),
                )

                action_requirement = cursor.fetchone()
                connection.commit()

                return action_requirement

    def delete_by_id(
        self,
        action_requirement_id: UUID,
    ) -> bool:
        """Delete an action requirement and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM action_requirements
                    WHERE id = %s
                    """,
                    (action_requirement_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
