"""
Assistance request repository.

Provides database access operations for the assistance_requests table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class AssistanceRequestsRepository:
    """Data access operations for assistance requests."""

    def get_by_id(
        self,
        assistance_request_id: UUID,
    ) -> dict[str, Any] | None:
        """Return an assistance request by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM assistance_requests
                    WHERE id = %s
                    """,
                    (assistance_request_id,),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all assistance requests for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM assistance_requests
                    WHERE organization_id = %s
                    ORDER BY requested_at
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_by_worker_profile_id(
        self,
        worker_profile_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all assistance requests for a worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM assistance_requests
                    WHERE worker_profile_id = %s
                    ORDER BY requested_at
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchall()

    def list_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        """Return all assistance requests with the given status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    FROM assistance_requests
                    WHERE status = %s
                    ORDER BY requested_at
                    """,
                    (status,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
        work_session_id: UUID | None = None,
        workflow_assignment_id: UUID | None = None,
        worker_task_assignment_id: UUID | None = None,
        priority: str = "normal",
        reason: str | None = None,
        request_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and return an assistance request."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO assistance_requests (
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        priority,
                        reason,
                        request_data
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        priority,
                        reason,
                        request_data or {},
                    ),
                )

                assistance_request = cursor.fetchone()
                connection.commit()

                return assistance_request

    def update_status(
        self,
        assistance_request_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update an assistance request status and return it."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE assistance_requests
                    SET
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (
                        status,
                        assistance_request_id,
                    ),
                )

                assistance_request = cursor.fetchone()
                connection.commit()

                return assistance_request

    def acknowledge(
        self,
        assistance_request_id: UUID,
    ) -> dict[str, Any] | None:
        """Acknowledge an assistance request."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE assistance_requests
                    SET
                        status = 'acknowledged',
                        acknowledged_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (assistance_request_id,),
                )

                assistance_request = cursor.fetchone()
                connection.commit()

                return assistance_request

    def resolve(
        self,
        assistance_request_id: UUID,
    ) -> dict[str, Any] | None:
        """Resolve an assistance request."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE assistance_requests
                    SET
                        status = 'resolved',
                        resolved_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        worker_profile_id,
                        work_session_id,
                        workflow_assignment_id,
                        worker_task_assignment_id,
                        status,
                        priority,
                        reason,
                        request_data,
                        requested_at,
                        acknowledged_at,
                        resolved_at,
                        created_at,
                        updated_at
                    """,
                    (assistance_request_id,),
                )

                assistance_request = cursor.fetchone()
                connection.commit()

                return assistance_request

    def delete_by_id(
        self,
        assistance_request_id: UUID,
    ) -> bool:
        """Delete an assistance request and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM assistance_requests
                    WHERE id = %s
                    """,
                    (assistance_request_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
