"""
Role permission repository.

Provides database access operations for the role_permissions table.
Every grant is organization-scoped (tenant isolation for the RBAC matrix).
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class RolePermissionsRepository:
    """Data access operations for organization-scoped role-permission grants."""

    def get_by_role_id(
        self,
        organization_id: UUID,
        role_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all permission grants for a role within an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT organization_id, role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE organization_id = %s
                      AND role_id = %s
                    ORDER BY created_at
                    """,
                    (organization_id, role_id),
                )
                return cursor.fetchall()

    def get_by_permission_id(
        self,
        organization_id: UUID,
        permission_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all role grants for a permission within an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT organization_id, role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE organization_id = %s
                      AND permission_id = %s
                    ORDER BY created_at
                    """,
                    (organization_id, permission_id),
                )
                return cursor.fetchall()

    def get(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_id: UUID,
    ) -> dict[str, Any] | None:
        """Return one organization-scoped assignment, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT organization_id, role_id, permission_id, created_at
                    FROM role_permissions
                    WHERE organization_id = %s
                      AND role_id = %s
                      AND permission_id = %s
                    """,
                    (organization_id, role_id, permission_id),
                )
                return cursor.fetchone()

    def create(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_id: UUID,
    ) -> dict[str, Any]:
        """Create and return an organization-scoped role-permission assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO role_permissions (
                        organization_id,
                        role_id,
                        permission_id
                    )
                    VALUES (%s, %s, %s)
                    RETURNING organization_id, role_id, permission_id, created_at
                    """,
                    (organization_id, role_id, permission_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_id: UUID,
    ) -> bool:
        """Delete an organization-scoped role-permission assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    DELETE FROM role_permissions
                    WHERE organization_id = %s
                      AND role_id = %s
                      AND permission_id = %s
                    """,
                    (organization_id, role_id, permission_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted

    def list_matrix(self, organization_id: UUID) -> list[dict[str, Any]]:
        """Return every (permission, role) grant for one organization, joined."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        p.id AS permission_id,
                        p.name AS permission_name,
                        p.description AS permission_description,
                        r.id AS role_id,
                        r.name AS role_name
                    FROM role_permissions rp
                    JOIN permissions p ON p.id = rp.permission_id
                    JOIN roles r ON r.id = rp.role_id
                    WHERE rp.organization_id = %s
                    ORDER BY p.name, r.name
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_role_names_for_user(self, user_id: UUID) -> list[str]:
        """Resolve a user's role names (single query)."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT r.name
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE ur.user_id = %s
                    ORDER BY r.name
                    """,
                    (user_id,),
                )
                return [row["name"] for row in cursor.fetchall()]

    def list_permission_names_for_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[str]:
        """Resolve a user's effective permission names within their organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT p.name
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    JOIN role_permissions rp
                        ON rp.role_id = r.id
                       AND rp.organization_id = %s
                    JOIN permissions p ON p.id = rp.permission_id
                    WHERE ur.user_id = %s
                    ORDER BY p.name
                    """,
                    (organization_id, user_id),
                )
                return [row["name"] for row in cursor.fetchall()]
