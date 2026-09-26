"""
User repository.

Provides database access operations for the users table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class UsersRepository:
    """Data access operations for users."""

    def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        """Return a user by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, email, full_name, password_hash,
                           status, created_at, updated_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                return cursor.fetchone()

    def get_by_email(
        self,
        organization_id: UUID,
        email: str,
    ) -> dict[str, Any] | None:
        """Return a user by organization and email, or None."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, email, full_name, password_hash,
                           status, created_at, updated_at
                    FROM users
                    WHERE organization_id = %s
                      AND email = %s
                    """,
                    (organization_id, email),
                )
                return cursor.fetchone()

    def list_by_organization(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all users for an organization ordered by full name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, email, full_name, password_hash,
                           status, created_at, updated_at
                    FROM users
                    WHERE organization_id = %s
                    ORDER BY full_name
                    """,
                    (organization_id,),
                )
                return list(cursor.fetchall())

    def create(
        self,
        organization_id: UUID,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> dict[str, Any]:
        """Create and return a user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (
                        organization_id,
                        email,
                        full_name,
                        password_hash
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, organization_id, email, full_name, password_hash,
                              status, created_at, updated_at
                    """,
                    (
                        organization_id,
                        email,
                        full_name,
                        password_hash,
                    ),
                )
                user = cursor.fetchone()
                connection.commit()

                return user

    def update_status(
        self,
        user_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update a user's account status and return the updated row (or None)."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, organization_id, email, full_name, password_hash,
                              status, created_at, updated_at
                    """,
                    (status, user_id),
                )
                updated = cursor.fetchone()
                connection.commit()
                return updated

    def delete_by_id(self, user_id: UUID) -> bool:
        """Delete a user by ID and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
