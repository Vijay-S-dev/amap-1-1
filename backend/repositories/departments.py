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
        """Return a department by organization and name (case-insensitive), or None."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, name, status,
                           created_at, updated_at
                    FROM departments
                    WHERE organization_id = %s
                      AND LOWER(name) = LOWER(%s)
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

    _COUNTED_SELECT = """
        SELECT
            d.id, d.organization_id, d.name, d.status,
            d.created_at, d.updated_at,
            (
                SELECT COUNT(*)
                FROM user_departments ud
                JOIN user_roles ur ON ur.user_id = ud.user_id
                JOIN roles r ON r.id = ur.role_id AND r.name = 'supervisor'
                WHERE ud.department_id = d.id
            ) AS supervisor_count,
            (
                SELECT COUNT(DISTINCT wp.id)
                FROM worker_profiles wp
                JOIN users u ON u.id = wp.user_id
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id AND r.name = 'worker'
                JOIN user_departments ud ON ud.user_id = u.id
                WHERE ud.department_id = d.id
                  AND u.status = 'active'
                  AND wp.status = 'active'
            ) AS worker_count,
            (
                SELECT COUNT(*)
                FROM worker_task_assignments wta
                JOIN worker_profiles wp ON wp.id = wta.worker_profile_id
                JOIN user_departments ud ON ud.user_id = wp.user_id
                WHERE ud.department_id = d.id
                  AND wta.status IN ('assigned', 'in_progress')
            ) AS active_tasks_count
        FROM departments d
    """

    def list_by_organization_with_counts(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return departments with real supervisor/worker/active-task counts."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    self._COUNTED_SELECT
                    + """
                    WHERE d.organization_id = %s
                    ORDER BY d.name
                    """,
                    (organization_id,),
                )
                return list(cursor.fetchall())

    def get_with_counts(self, department_id: UUID) -> dict[str, Any] | None:
        """Return one department with real supervisor/worker/active-task counts."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    self._COUNTED_SELECT + " WHERE d.id = %s",
                    (department_id,),
                )
                return cursor.fetchone()

    def update(
        self,
        department_id: UUID,
        name: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        """Persist name and/or status changes; returns the updated row."""
        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if not sets:
            return None
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(department_id)

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    UPDATE departments
                    SET {", ".join(sets)}
                    WHERE id = %s
                    RETURNING id, organization_id, name, status,
                              created_at, updated_at
                    """,
                    tuple(params),
                )
                updated = cursor.fetchone()
                connection.commit()
                return updated

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
