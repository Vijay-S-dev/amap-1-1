"""
User department repository.

Provides database access operations for the user_departments table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class UserDepartmentsRepository:
    """Data access operations for user-department assignments."""

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all department assignments for a user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, department_id, created_at
                    FROM user_departments
                    WHERE user_id = %s
                    ORDER BY created_at
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

    def get_by_department_id(
        self,
        department_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all user assignments for a department."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, department_id, created_at
                    FROM user_departments
                    WHERE department_id = %s
                    ORDER BY created_at
                    """,
                    (department_id,),
                )
                return cursor.fetchall()

    def get(
        self,
        user_id: UUID,
        department_id: UUID,
    ) -> dict[str, Any] | None:
        """Return one user-department assignment, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, department_id, created_at
                    FROM user_departments
                    WHERE user_id = %s
                      AND department_id = %s
                    """,
                    (user_id, department_id),
                )
                return cursor.fetchone()

    def create(
        self,
        user_id: UUID,
        department_id: UUID,
    ) -> dict[str, Any]:
        """Create and return a user-department assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_departments (
                        user_id,
                        department_id
                    )
                    VALUES (%s, %s)
                    RETURNING user_id, department_id, created_at
                    """,
                    (user_id, department_id),
                )

                assignment = cursor.fetchone()
                connection.commit()

                return assignment

    def delete(
        self,
        user_id: UUID,
        department_id: UUID,
    ) -> bool:
        """Delete a user-department assignment."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM user_departments
                    WHERE user_id = %s
                      AND department_id = %s
                    """,
                    (user_id, department_id),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
