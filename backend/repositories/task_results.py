"""
Task result repository.

Provides database access operations for the task_results table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class TaskResultsRepository:
    """Data access operations for task results."""

    def get_by_id(
        self,
        task_result_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a task result by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                        recorded_at,
                        created_at,
                        updated_at
                    FROM task_results
                    WHERE id = %s
                    """,
                    (task_result_id,),
                )
                return cursor.fetchone()

    def get_by_worker_task_assignment_id(
        self,
        worker_task_assignment_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the task result for a worker task assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                        recorded_at,
                        created_at,
                        updated_at
                    FROM task_results
                    WHERE worker_task_assignment_id = %s
                    """,
                    (worker_task_assignment_id,),
                )
                return cursor.fetchone()

    def list_by_outcome(
        self,
        outcome: str,
    ) -> list[dict[str, Any]]:
        """Return all task results with the given outcome."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                        recorded_at,
                        created_at,
                        updated_at
                    FROM task_results
                    WHERE outcome = %s
                    ORDER BY recorded_at
                    """,
                    (outcome,),
                )
                return cursor.fetchall()

    def create(
        self,
        worker_task_assignment_id: UUID,
        outcome: str,
        result_data: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a task result."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO task_results (
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                        recorded_at,
                        created_at,
                        updated_at
                    """,
                    (
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                    ),
                )

                task_result = cursor.fetchone()
                connection.commit()

                return task_result

    def update(
        self,
        task_result_id: UUID,
        outcome: str,
        result_data: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        """Update and return a task result, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE task_results
                    SET
                        outcome = %s,
                        result_data = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_task_assignment_id,
                        outcome,
                        result_data,
                        notes,
                        recorded_at,
                        created_at,
                        updated_at
                    """,
                    (
                        outcome,
                        result_data,
                        notes,
                        task_result_id,
                    ),
                )

                task_result = cursor.fetchone()
                connection.commit()

                return task_result

    def delete_by_id(
        self,
        task_result_id: UUID,
    ) -> bool:
        """Delete a task result and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM task_results
                    WHERE id = %s
                    """,
                    (task_result_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
