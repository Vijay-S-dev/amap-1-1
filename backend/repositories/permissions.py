"""
Permission repository.

Provides database access operations for the permissions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class PermissionsRepository:
    """Data access operations for permissions."""

    def get_by_id(
        self,
        permission_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a permission by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM permissions
                    WHERE id = %s
                    """,
                    (permission_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a permission by its name, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM permissions
                    WHERE name = %s
                    """,
                    (name,),
                )
                return cursor.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all permissions ordered by name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM permissions
                    ORDER BY name
                    """
                )
                return cursor.fetchall()

    def create(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a permission."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO permissions (
                        name,
                        description
                    )
                    VALUES (%s, %s)
                    RETURNING id, name, description, created_at, updated_at
                    """,
                    (name, description),
                )

                permission = cursor.fetchone()
                connection.commit()

                return permission

    def delete_by_id(
        self,
        permission_id: UUID,
    ) -> bool:
        """Delete a permission and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM permissions
                    WHERE id = %s
                    """,
                    (permission_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
