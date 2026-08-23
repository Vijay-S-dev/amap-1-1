"""
Worker personalizations repository.

Provides database access operations for the worker_personalizations table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class WorkerPersonalizationsRepository:
    """Data access operations for worker personalizations."""

    def get_by_id(
        self,
        worker_personalization_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker personalization by ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        interaction_configuration_id,
                        personalization_data,
                        status,
                        created_at,
                        updated_at
                    FROM worker_personalizations
                    WHERE id = %s
                    """,
                    (worker_personalization_id,),
                )
                return cursor.fetchone()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all personalizations for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        interaction_configuration_id,
                        personalization_data,
                        status,
                        created_at,
                        updated_at
                    FROM worker_personalizations
                    WHERE worker_profile_id = %s
                    ORDER BY created_at
                    """,
                    (worker_profile_id,),
                )
                return list(cursor.fetchall())

    def create(
        self,
        worker_profile_id: UUID,
        interaction_configuration_id: UUID | None = None,
        personalization_data: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a worker personalization."""
        if personalization_data is None:
            personalization_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_personalizations (
                        worker_profile_id,
                        interaction_configuration_id,
                        personalization_data,
                        status
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING
                        id,
                        worker_profile_id,
                        interaction_configuration_id,
                        personalization_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        worker_profile_id,
                        interaction_configuration_id,
                        Jsonb(personalization_data),
                        status,
                    ),
                )

                worker_personalization = cursor.fetchone()
                connection.commit()

                return worker_personalization

    def update(
        self,
        worker_personalization_id: UUID,
        interaction_configuration_id: UUID | None,
        personalization_data: dict[str, Any],
        status: str,
    ) -> dict[str, Any] | None:
        """Update a worker personalization and return it."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE worker_personalizations
                    SET
                        interaction_configuration_id = %s,
                        personalization_data = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        interaction_configuration_id,
                        personalization_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        interaction_configuration_id,
                        Jsonb(personalization_data),
                        status,
                        worker_personalization_id,
                    ),
                )

                worker_personalization = cursor.fetchone()
                connection.commit()

                return worker_personalization

    def delete_by_id(
        self,
        worker_personalization_id: UUID,
    ) -> bool:
        """Delete a worker personalization and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_personalizations
                    WHERE id = %s
                    """,
                    (worker_personalization_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
