"""
Role repository.

Provides database access operations for the roles table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class RolesRepository:
    """Data access operations for roles."""

    def get_by_id(
        self,
        role_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a role by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM roles
                    WHERE id = %s
                    """,
                    (role_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a role by its name, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM roles
                    WHERE name = %s
                    """,
                    (name,),
                )
                return cursor.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all roles ordered by name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM roles
                    ORDER BY name
                    """
                )
                return cursor.fetchall()

    def create(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a role."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO roles (
                        name,
                        description
                    )
                    VALUES (%s, %s)
                    RETURNING id, name, description, created_at, updated_at
                    """,
                    (name, description),
                )

                role = cursor.fetchone()
                connection.commit()

                return role

    def delete_by_id(
        self,
        role_id: UUID,
    ) -> bool:
        """Delete a role and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM roles
                    WHERE id = %s
                    """,
                    (role_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
