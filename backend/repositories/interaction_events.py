"""
Interaction event repository.

Provides database access operations for the interaction_events table.
Business logic does not belong in this module.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.database import get_db_connection


class InteractionEventsRepository:
    """Data access operations for interaction events."""

    def get_by_id(
        self,
        interaction_event_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an interaction event by ID."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE id = %s
                    """,
                    (interaction_event_id,),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return interaction events for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE organization_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return interaction events for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE worker_profile_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def list_by_work_session_id(
        self,
        work_session_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return interaction events for a work session."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE work_session_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (work_session_id,),
                )
                return cursor.fetchall()

    def list_by_action_id(
        self,
        action_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return interaction events for an action."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE action_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (action_id,),
                )
                return cursor.fetchall()

    def list_by_event_type(
        self,
        event_type: str,
    ) -> list[dict[str, Any]]:
        """Return interaction events by event type."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    FROM interaction_events
                    WHERE event_type = %s
                    ORDER BY occurred_at DESC
                    """,
                    (event_type,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
        interaction_mode: str,
        event_type: str,
        work_session_id: UUID | None = None,
        action_id: UUID | None = None,
        confidence: Decimal | float | None = None,
        interaction_data: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create and return an interaction event."""
        if interaction_data is None:
            interaction_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO interaction_events (
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        COALESCE(%s, CURRENT_TIMESTAMP)
                    )
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        interaction_data,
                        occurred_at,
                        created_at
                    """,
                    (
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        action_id,
                        interaction_mode,
                        event_type,
                        confidence,
                        Json(interaction_data),
                        occurred_at,
                    ),
                )

                interaction_event = cursor.fetchone()
                connection.commit()

                return interaction_event

    def delete_by_id(
        self,
        interaction_event_id: UUID,
    ) -> bool:
        """Delete an interaction event."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM interaction_events
                    WHERE id = %s
                    """,
                    (interaction_event_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
