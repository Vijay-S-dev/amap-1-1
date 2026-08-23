"""
Gesture configuration repository.

Provides database access operations for the gesture_configurations table.
Business logic does not belong in this module.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class GestureConfigurationsRepository:
    """Data access operations for gesture configurations."""

    def get_by_id(
        self,
        gesture_configuration_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a gesture configuration by ID."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM gesture_configurations
                    WHERE id = %s
                    """,
                    (gesture_configuration_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        interaction_configuration_id: UUID,
        gesture_name: str,
    ) -> dict[str, Any] | None:
        """Return a gesture configuration by configuration and gesture name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM gesture_configurations
                    WHERE interaction_configuration_id = %s
                      AND gesture_name = %s
                    """,
                    (
                        interaction_configuration_id,
                        gesture_name,
                    ),
                )
                return cursor.fetchone()

    def list_by_interaction_configuration_id(
        self,
        interaction_configuration_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return gesture configurations for an interaction configuration."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM gesture_configurations
                    WHERE interaction_configuration_id = %s
                    ORDER BY gesture_name
                    """,
                    (interaction_configuration_id,),
                )
                return cursor.fetchall()

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return gesture configurations for an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM gesture_configurations
                    WHERE action_id = %s
                    ORDER BY gesture_name
                    """,
                    (action_id,),
                )
                return cursor.fetchall()

    def create(
        self,
        interaction_configuration_id: UUID,
        gesture_name: str,
        action_id: UUID,
        is_enabled: bool = True,
        confidence_threshold: Decimal | float | None = None,
    ) -> dict[str, Any]:
        """Create and return a gesture configuration."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO gesture_configurations (
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    """,
                    (
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                    ),
                )

                gesture_configuration = cursor.fetchone()
                connection.commit()

                return gesture_configuration

    def update_enabled(
        self,
        gesture_configuration_id: UUID,
        is_enabled: bool,
    ) -> dict[str, Any] | None:
        """Update whether a gesture configuration is enabled."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE gesture_configurations
                    SET
                        is_enabled = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        interaction_configuration_id,
                        gesture_name,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    """,
                    (
                        is_enabled,
                        gesture_configuration_id,
                    ),
                )

                gesture_configuration = cursor.fetchone()
                connection.commit()

                return gesture_configuration

    def delete_by_id(
        self,
        gesture_configuration_id: UUID,
    ) -> bool:
        """Delete a gesture configuration."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM gesture_configurations
                    WHERE id = %s
                    """,
                    (gesture_configuration_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
