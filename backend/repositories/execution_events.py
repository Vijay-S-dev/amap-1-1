"""
Execution event repository.

Provides database access operations for the execution_events table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class ExecutionEventsRepository:
    """Data access operations for execution events."""

    def get_by_id(
        self,
        execution_event_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an execution event by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
                    WHERE id = %s
                    """,
                    (execution_event_id,),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return execution events for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
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
        """Return execution events for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
                    WHERE worker_profile_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def list_by_workflow_assignment_id(
        self,
        workflow_assignment_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return execution events for a workflow assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
                    WHERE workflow_assignment_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (workflow_assignment_id,),
                )
                return cursor.fetchall()

    def list_by_worker_task_assignment_id(
        self,
        worker_task_assignment_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return execution events for a worker task assignment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
                    WHERE worker_task_assignment_id = %s
                    ORDER BY occurred_at DESC
                    """,
                    (worker_task_assignment_id,),
                )
                return cursor.fetchall()

    def list_by_event_type(
        self,
        event_type: str,
    ) -> list[dict[str, Any]]:
        """Return execution events with the given event type."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    FROM execution_events
                    WHERE event_type = %s
                    ORDER BY occurred_at DESC
                    """,
                    (event_type,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        event_type: str,
        worker_profile_id: UUID | None = None,
        workflow_assignment_id: UUID | None = None,
        worker_task_assignment_id: UUID | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and return an execution event."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO execution_events (
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        event_data,
                        occurred_at,
                        created_at
                    """,
                    (
                        organization_id,
                        worker_profile_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        event_type,
                        Jsonb(event_data or {}),
                    ),
                )

                execution_event = cursor.fetchone()
                connection.commit()

                return execution_event

    def delete_by_id(
        self,
        execution_event_id: UUID,
    ) -> bool:
        """Delete an execution event and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM execution_events
                    WHERE id = %s
                    """,
                    (execution_event_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
