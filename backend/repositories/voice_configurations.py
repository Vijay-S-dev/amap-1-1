"""
Voice configuration repository.

Provides database access operations for the voice_configurations table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class VoiceConfigurationsRepository:
    """Data access operations for voice configurations."""

    def _normalize_row(
        self,
        row: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Normalize database values for repository consumers."""
        if row is not None and row["confidence_threshold"] is not None:
            row["confidence_threshold"] = float(
                row["confidence_threshold"]
            )
        return row

    def get_by_id(
        self,
        voice_configuration_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a voice configuration by its ID, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM voice_configurations
                    WHERE id = %s
                    """,
                    (voice_configuration_id,),
                )

                return self._normalize_row(cursor.fetchone())

    def get_by_command_phrase(
        self,
        interaction_configuration_id: UUID,
        command_phrase: str,
    ) -> dict[str, Any] | None:
        """Return a configuration by interaction configuration and phrase."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM voice_configurations
                    WHERE interaction_configuration_id = %s
                      AND command_phrase = %s
                    """,
                    (
                        interaction_configuration_id,
                        command_phrase,
                    ),
                )

                return self._normalize_row(cursor.fetchone())

    def list_by_interaction_configuration_id(
        self,
        interaction_configuration_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all voice configurations for an interaction configuration."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM voice_configurations
                    WHERE interaction_configuration_id = %s
                    ORDER BY command_phrase
                    """,
                    (interaction_configuration_id,),
                )

                rows = cursor.fetchall()
                return [
                    self._normalize_row(row)
                    for row in rows
                ]

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all voice configurations using an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    FROM voice_configurations
                    WHERE action_id = %s
                    ORDER BY command_phrase
                    """,
                    (action_id,),
                )

                rows = cursor.fetchall()
                return [
                    self._normalize_row(row)
                    for row in rows
                ]

    def create(
        self,
        interaction_configuration_id: UUID,
        command_phrase: str,
        action_id: UUID,
        is_enabled: bool = True,
        confidence_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Create and return a voice configuration."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO voice_configurations (
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    """,
                    (
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                    ),
                )

                voice_configuration = self._normalize_row(
                    cursor.fetchone()
                )
                connection.commit()

                return voice_configuration

    def update(
        self,
        voice_configuration_id: UUID,
        command_phrase: str,
        action_id: UUID,
        is_enabled: bool,
        confidence_threshold: float | None,
    ) -> dict[str, Any] | None:
        """Update a voice configuration and return it, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE voice_configurations
                    SET
                        command_phrase = %s,
                        action_id = %s,
                        is_enabled = %s,
                        confidence_threshold = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        interaction_configuration_id,
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        created_at,
                        updated_at
                    """,
                    (
                        command_phrase,
                        action_id,
                        is_enabled,
                        confidence_threshold,
                        voice_configuration_id,
                    ),
                )

                voice_configuration = self._normalize_row(
                    cursor.fetchone()
                )
                connection.commit()

                return voice_configuration

    def delete_by_id(
        self,
        voice_configuration_id: UUID,
    ) -> bool:
        """Delete a voice configuration and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM voice_configurations
                    WHERE id = %s
                    """,
                    (voice_configuration_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
