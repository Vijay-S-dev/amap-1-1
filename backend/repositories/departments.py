"""
Department repository.

Provides database access operations for the departments table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class DepartmentsRepository:
    """Data access operations for departments."""

    def get_by_id(self, department_id: UUID) -> dict[str, Any] | None:
        """Return a department by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, name, status,
                           created_at, updated_at
                    FROM departments
                    WHERE id = %s
                    """,
                    (department_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a department by organization and name, or None."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, name, status,
                           created_at, updated_at
                    FROM departments
                    WHERE organization_id = %s
                      AND name = %s
                    """,
                    (organization_id, name),
                )
                return cursor.fetchone()

    def list_by_organization(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all departments for an organization ordered by name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, name, status,
                           created_at, updated_at
                    FROM departments
                    WHERE organization_id = %s
                    ORDER BY name
                    """,
                    (organization_id,),
                )
                return list(cursor.fetchall())

    def create(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any]:
        """Create and return a department."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO departments (organization_id, name)
                    VALUES (%s, %s)
                    RETURNING id, organization_id, name, status,
                              created_at, updated_at
                    """,
                    (organization_id, name),
                )
                department = cursor.fetchone()
                connection.commit()

                return department

    def delete_by_id(self, department_id: UUID) -> bool:
        """Delete a department by ID and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM departments
                    WHERE id = %s
                    """,
                    (department_id,),
                )
                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
