"""
Audit event repository.

Provides database access operations for the audit_events table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class AuditEventsRepository:
    """Data access operations for audit events."""

    def get_by_id(
        self,
        audit_event_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an audit event by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    FROM audit_events
                    WHERE id = %s
                    """,
                    (audit_event_id,),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all audit events for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    FROM audit_events
                    WHERE organization_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_by_actor_user_id(
        self,
        actor_user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all audit events performed by a user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    FROM audit_events
                    WHERE actor_user_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (actor_user_id,),
                )
                return cursor.fetchall()

    def list_by_event_type(
        self,
        event_type: str,
    ) -> list[dict[str, Any]]:
        """Return all audit events with a given event type."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    FROM audit_events
                    WHERE event_type = %s
                    ORDER BY occurred_at DESC
                    """,
                    (event_type,),
                )
                return cursor.fetchall()

    def list_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all audit events for a specific resource."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    FROM audit_events
                    WHERE resource_type = %s
                      AND resource_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (
                        resource_type,
                        resource_id,
                    ),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        event_type: str,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and return an audit event."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        event_data,
                        occurred_at,
                        created_at
                    """,
                    (
                        organization_id,
                        actor_user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        Jsonb(event_data or {}),
                    ),
                )

                audit_event = cursor.fetchone()
                connection.commit()

                return audit_event

    def delete_by_id(
        self,
        audit_event_id: UUID,
    ) -> bool:
        """Delete an audit event and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM audit_events
                    WHERE id = %s
                    """,
                    (audit_event_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
