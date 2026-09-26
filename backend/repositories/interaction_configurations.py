"""
Interaction configuration repository.

Provides database access operations for the interaction_configurations table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class InteractionConfigurationsRepository:
    """Data access operations for interaction configurations."""

    def get_by_id(
        self,
        interaction_configuration_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an interaction configuration by ID."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    FROM interaction_configurations
                    WHERE id = %s
                    """,
                    (interaction_configuration_id,),
                )
                return cursor.fetchone()

    def get_by_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return an interaction configuration by organization and name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    FROM interaction_configurations
                    WHERE organization_id = %s
                      AND name = %s
                    """,
                    (organization_id, name),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all interaction configurations for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    FROM interaction_configurations
                    WHERE organization_id = %s
                    ORDER BY name
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        """Return all interaction configurations with the given status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    FROM interaction_configurations
                    WHERE status = %s
                    ORDER BY name
                    """,
                    (status,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        status: str = "active",
        config_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and return an interaction configuration with its payload."""
        import json as _json
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO interaction_configurations (
                        organization_id,
                        name,
                        description,
                        config_data,
                        status
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        organization_id,
                        name,
                        description,
                        _json.dumps(config_data or {}),
                        status,
                    ),
                )

                interaction_configuration = cursor.fetchone()
                connection.commit()

                return interaction_configuration

    def update_status(
        self,
        interaction_configuration_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update an interaction configuration status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE interaction_configurations
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        interaction_configuration_id,
                    ),
                )

                interaction_configuration = cursor.fetchone()
                connection.commit()

                return interaction_configuration

    def update(
        self,
        interaction_configuration_id: UUID,
        name: str,
        description: str | None = None,
        status: str = "active",
        config_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update name/description/status/config_data and return the new row."""
        import json as _json
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE interaction_configurations
                    SET
                        name = %s,
                        description = %s,
                        status = %s,
                        config_data = %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        config_data,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        name,
                        description,
                        status,
                        _json.dumps(config_data if config_data is not None else {}),
                        interaction_configuration_id,
                    ),
                )

                interaction_configuration = cursor.fetchone()
                connection.commit()

                return interaction_configuration

    def delete_by_id(
        self,
        interaction_configuration_id: UUID,
    ) -> bool:
        """Delete an interaction configuration."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM interaction_configurations
                    WHERE id = %s
                    """,
                    (interaction_configuration_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
