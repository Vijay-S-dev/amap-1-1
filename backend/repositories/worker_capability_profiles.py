"""
Worker capability profile repository.

Provides database access operations for the worker_capability_profiles table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class WorkerCapabilityProfilesRepository:
    """Data access operations for worker capability profiles."""

    def get_by_id(
        self,
        worker_capability_profile_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker capability profile by its ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    FROM worker_capability_profiles
                    WHERE id = %s
                    """,
                    (worker_capability_profile_id,),
                )
                return cursor.fetchone()

    def get_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the capability profile for a worker, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    FROM worker_capability_profiles
                    WHERE worker_profile_id = %s
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchone()

    def list_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        """Return all worker capability profiles with the given status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    FROM worker_capability_profiles
                    WHERE status = %s
                    ORDER BY created_at
                    """,
                    (status,),
                )
                return cursor.fetchall()

    def create(
        self,
        worker_profile_id: UUID,
        capability_data: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a worker capability profile."""
        if capability_data is None:
            capability_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_capability_profiles (
                        worker_profile_id,
                        capability_data,
                        status
                    )
                    VALUES (%s, %s, %s)
                    RETURNING
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        worker_profile_id,
                        Jsonb(capability_data),
                        status,
                    ),
                )

                worker_capability_profile = cursor.fetchone()
                connection.commit()

                return worker_capability_profile

    def update(
        self,
        worker_capability_profile_id: UUID,
        capability_data: dict[str, Any],
        status: str,
    ) -> dict[str, Any] | None:
        """Update a capability profile and return it, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE worker_capability_profiles
                    SET
                        capability_data = %s,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        Jsonb(capability_data),
                        status,
                        worker_capability_profile_id,
                    ),
                )

                worker_capability_profile = cursor.fetchone()
                connection.commit()

                return worker_capability_profile

    def update_status(
        self,
        worker_capability_profile_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update a capability profile status and return it."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE worker_capability_profiles
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        worker_profile_id,
                        capability_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        worker_capability_profile_id,
                    ),
                )

                worker_capability_profile = cursor.fetchone()
                connection.commit()

                return worker_capability_profile

    def delete_by_id(
        self,
        worker_capability_profile_id: UUID,
    ) -> bool:
        """Delete a worker capability profile and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_capability_profiles
                    WHERE id = %s
                    """,
                    (worker_capability_profile_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
