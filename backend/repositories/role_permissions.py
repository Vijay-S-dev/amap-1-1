"""
Role permission repository.

Provides database access operations for the role_permissions table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class RolePermissionsRepository:
    """Data access operations for role-permission assignments."""

    def get_by_role_id(
        self,
        role_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all permission assignments for a role."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE role_id = %s
                    ORDER BY created_at
                    """,
                    (role_id,),
                )
                return cursor.fetchall()

    def get_by_permission_id(
        self,
        permission_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all role assignments for a permission."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE permission_id = %s
                    ORDER BY created_at
                    """,
                    (permission_id,),
                )
                return cursor.fetchall()

    def get(
        self,
        role_id: UUID,
        permission_id: UUID,
    ) -> dict[str, Any] | None:
        """Return one role-permission assignment, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE role_id = %s
                      AND permission_id = %s
                    """,
                    (role_id, permission_id),
                )
                return cursor.fetchone()

    def create(
        self,
        role_id: UUID,
        permission_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a role-permission assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO role_permissions (
                        role_id,
                        permission_id
                    )
                    VALUES (%s, %s)
                    RETURNING role_id, permission_id, created_at
                    """,
                    (role_id, permission_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete(
        self,
        role_id: UUID,
        permission_id: UUID,
    ) -> bool:
        """Delete a role-permission assignment."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM role_permissions
                    WHERE role_id = %s
                      AND permission_id = %s
                    """,
                    (role_id, permission_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
