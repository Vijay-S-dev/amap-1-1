"""
Assistance and Notification service for AMAP.

Orchestrates worker assistance requests and delivers notifications across organizations.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from models.assistance import (
    AssistanceRequestCreate,
    AssistanceRequestRead,
    NotificationCreate,
    NotificationRead,
)
from repositories.assistance_requests import AssistanceRequestsRepository
from repositories.notifications import NotificationsRepository
from services.base import NotFoundError, UnauthorizedError, ValidationError


class AssistanceService:
    """Business logic for worker assistance requests and notifications."""

    def __init__(
        self,
        assistance_repo: Optional[AssistanceRequestsRepository] = None,
        notifications_repo: Optional[NotificationsRepository] = None,
    ) -> None:
        self.assistance_repo = assistance_repo or AssistanceRequestsRepository()
        self.notifications_repo = notifications_repo or NotificationsRepository()

    def create_assistance_request(
        self,
        payload: AssistanceRequestCreate,
    ) -> AssistanceRequestRead:
        """Create a new worker assistance request."""
        created = self.assistance_repo.create(
            organization_id=payload.organization_id,
            worker_profile_id=payload.worker_profile_id,
            work_session_id=payload.work_session_id,
            workflow_assignment_id=payload.workflow_assignment_id,
            worker_task_assignment_id=payload.worker_task_assignment_id,
            priority=payload.priority,
            reason=payload.reason,
            request_data=payload.request_data,
        )
        return AssistanceRequestRead.model_validate(created)

    def acknowledge_request(
        self,
        request_id: UUID,
        organization_id: UUID,
    ) -> AssistanceRequestRead:
        """Acknowledge an open assistance request."""
        existing = self.assistance_repo.get_by_id(request_id)
        if not existing:
            raise NotFoundError(f"Assistance request {request_id} not found.")

        if existing["organization_id"] != organization_id:
            raise UnauthorizedError("Assistance request does not belong to this organization.")

        updated = self.assistance_repo.acknowledge(request_id)
        return AssistanceRequestRead.model_validate(updated)

    def resolve_request(
        self,
        request_id: UUID,
        organization_id: UUID,
    ) -> AssistanceRequestRead:
        """Resolve an assistance request."""
        existing = self.assistance_repo.get_by_id(request_id)
        if not existing:
            raise NotFoundError(f"Assistance request {request_id} not found.")

        if existing["organization_id"] != organization_id:
            raise UnauthorizedError("Assistance request does not belong to this organization.")

        updated = self.assistance_repo.resolve(request_id)
        return AssistanceRequestRead.model_validate(updated)

    def send_notification(
        self,
        payload: NotificationCreate,
    ) -> NotificationRead:
        """Send a notification to a specific recipient user."""
        created = self.notifications_repo.create(
            organization_id=payload.organization_id,
            recipient_user_id=payload.recipient_user_id,
            notification_type=payload.notification_type,
            title=payload.title,
            message=payload.message,
            notification_data=payload.notification_data,
            status=payload.status,
        )
        return NotificationRead.model_validate(created)

    def mark_notification_as_read(
        self,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> NotificationRead:
        """Mark a user notification as read."""
        existing = self.notifications_repo.get_by_id(notification_id)
        if not existing:
            raise NotFoundError(f"Notification {notification_id} not found.")

        if existing["recipient_user_id"] != recipient_user_id:
            raise UnauthorizedError("Notification does not belong to this user.")

        updated = self.notifications_repo.mark_as_read(notification_id)
        return NotificationRead.model_validate(updated)
