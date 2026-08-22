"""
User role repository.

Provides database access operations for the user_roles table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class UserRolesRepository:
    """Data access operations for user-role assignments."""

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all role assignments for a user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, role_id, created_at
                    FROM user_roles
                    WHERE user_id = %s
                    ORDER BY created_at
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

    def get_by_role_id(
        self,
        role_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all user assignments for a role."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, role_id, created_at
                    FROM user_roles
                    WHERE role_id = %s
                    ORDER BY created_at
                    """,
                    (role_id,),
                )
                return cursor.fetchall()

    def get(
        self,
        user_id: UUID,
        role_id: UUID,
    ) -> dict[str, Any] | None:
        """Return one user-role assignment, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, role_id, created_at
                    FROM user_roles
                    WHERE user_id = %s
                      AND role_id = %s
                    """,
                    (user_id, role_id),
                )
                return cursor.fetchone()

    def create(
        self,
        user_id: UUID,
        role_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a user-role assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_roles (
                        user_id,
                        role_id
                    )
                    VALUES (%s, %s)
                    RETURNING user_id, role_id, created_at
                    """,
                    (user_id, role_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete(
        self,
        user_id: UUID,
        role_id: UUID,
    ) -> bool:
        """Delete a user-role assignment."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM user_roles
                    WHERE user_id = %s
                      AND role_id = %s
                    """,
                    (user_id, role_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
