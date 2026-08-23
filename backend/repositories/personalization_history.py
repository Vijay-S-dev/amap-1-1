"""
Personalization history repository.

Provides database access operations for the personalization_history table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class PersonalizationHistoryRepository:
    """Data access operations for personalization history."""

    def get_by_id(
        self,
        personalization_history_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a personalization history record by ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_personalization_id,
                        personalization_data,
                        change_reason,
                        changed_at,
                        created_at
                    FROM personalization_history
                    WHERE id = %s
                    """,
                    (personalization_history_id,),
                )

                return cursor.fetchone()

    def list_by_worker_personalization_id(
        self,
        worker_personalization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return personalization history for a worker personalization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_personalization_id,
                        personalization_data,
                        change_reason,
                        changed_at,
                        created_at
                    FROM personalization_history
                    WHERE worker_personalization_id = %s
                    ORDER BY changed_at DESC, created_at DESC
                    """,
                    (worker_personalization_id,),
                )

                return list(cursor.fetchall())

    def create(
        self,
        worker_personalization_id: UUID,
        personalization_data: dict[str, Any] | None = None,
        change_reason: str | None = None,
    ) -> dict[str, Any]:
        """Create and return a personalization history record."""
        if personalization_data is None:
            personalization_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO personalization_history (
                        worker_personalization_id,
                        personalization_data,
                        change_reason
                    )
                    VALUES (%s, %s, %s)
                    RETURNING
                        id,
                        worker_personalization_id,
                        personalization_data,
                        change_reason,
                        changed_at,
                        created_at
                    """,
                    (
                        worker_personalization_id,
                        Jsonb(personalization_data),
                        change_reason,
                    ),
                )

                history_record = cursor.fetchone()
                connection.commit()

                return history_record

    def delete_by_id(
        self,
        personalization_history_id: UUID,
    ) -> bool:
        """Delete a personalization history record and return success status."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM personalization_history
                    WHERE id = %s
                    """,
                    (personalization_history_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
