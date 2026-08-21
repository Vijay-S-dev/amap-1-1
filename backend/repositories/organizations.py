"""
Organization repository.

Provides database access operations for the organizations table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class OrganizationsRepository:
    """Data access operations for organizations."""

    def get_by_id(self, organization_id: UUID) -> dict[str, Any] | None:
        """Return an organization by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, created_at, updated_at
                    FROM organizations
                    WHERE id = %s
                    """,
                    (organization_id,),
                )
                return cursor.fetchone()

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Return an organization by its name, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, created_at, updated_at
                    FROM organizations
                    WHERE name = %s
                    """,
                    (name,),
                )
                return cursor.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all organizations ordered by name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, created_at, updated_at
                    FROM organizations
                    ORDER BY name
                    """
                )
                return list(cursor.fetchall())

    def create(self, name: str) -> dict[str, Any]:
        """Create and return an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO organizations (name)
                    VALUES (%s)
                    RETURNING id, name, status, created_at, updated_at
                    """,
                    (name,),
                )
                organization = cursor.fetchone()
                connection.commit()

                return organization

    def delete_by_id(self, organization_id: UUID) -> bool:
        """
        Delete an organization by ID.

        Returns True if an organization was deleted, otherwise False.
        """
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM organizations
                    WHERE id = %s
                    """,
                    (organization_id,),
                )
                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
