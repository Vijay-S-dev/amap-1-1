"""
Notification repository.

Provides database access operations for the notifications table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_db_connection


class NotificationsRepository:
    """Data access operations for notifications."""

    def get_by_id(
        self,
        notification_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a notification by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    FROM notifications
                    WHERE id = %s
                    """,
                    (notification_id,),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return notifications for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    FROM notifications
                    WHERE organization_id = %s
                    ORDER BY created_at DESC
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_by_recipient_user_id(
        self,
        recipient_user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return notifications for a recipient user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    FROM notifications
                    WHERE recipient_user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (recipient_user_id,),
                )
                return cursor.fetchall()

    def list_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        """Return notifications with the specified status."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    FROM notifications
                    WHERE status = %s
                    ORDER BY created_at DESC
                    """,
                    (status,),
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        recipient_user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        notification_data: dict[str, Any] | None = None,
        status: str = "unread",
    ) -> dict[str, Any]:
        """Create and return a notification."""
        if notification_data is None:
            notification_data = {}

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO notifications (
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    """,
                    (
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        Jsonb(notification_data),
                        status,
                    ),
                )

                notification = cursor.fetchone()
                connection.commit()

                return notification

    def update_status(
        self,
        notification_id: UUID,
        status: str,
    ) -> dict[str, Any] | None:
        """Update a notification status and return it, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE notifications
                    SET
                        status = %s,
                        read_at = CASE
                            WHEN %s = 'read' AND read_at IS NULL
                                THEN CURRENT_TIMESTAMP
                            ELSE read_at
                        END
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    """,
                    (
                        status,
                        status,
                        notification_id,
                    ),
                )

                notification = cursor.fetchone()
                connection.commit()

                return notification

    def mark_as_read(
        self,
        notification_id: UUID,
    ) -> dict[str, Any] | None:
        """Mark a notification as read and return it, or None if absent."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE notifications
                    SET
                        status = 'read',
                        read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        recipient_user_id,
                        notification_type,
                        title,
                        message,
                        notification_data,
                        status,
                        created_at,
                        read_at
                    """,
                    (notification_id,),
                )

                notification = cursor.fetchone()
                connection.commit()

                return notification

    def delete_by_id(
        self,
        notification_id: UUID,
    ) -> bool:
        """Delete a notification and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM notifications
                    WHERE id = %s
                    """,
                    (notification_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted

          
