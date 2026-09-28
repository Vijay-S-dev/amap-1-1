"""
Supervisor and Fleet Operations domain schemas for AMAP.

Defines schemas for real-time live monitoring, worker inspection, task assignment,
assistance triage, operational analytics, and audit timelines.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel


class SupervisorDashboardSummary(AMAPBaseModel):
    """Real-time summary KPIs for the supervisor's organization."""
    active_workers_count: int = Field(0, description="Workers currently with active work sessions")
    available_workers_count: int = Field(0, description="Active workers ready for task assignment")
    workers_in_task_count: int = Field(0, description="Workers currently executing tasks")
    workers_requesting_assistance_count: int = Field(0, description="Workers with open/acknowledged assistance requests")
    completed_tasks_count: int = Field(0, description="Total completed tasks in organization")
    in_progress_tasks_count: int = Field(0, description="Tasks currently in progress")
    failed_tasks_count: int = Field(0, description="Tasks blocked or failed")
    current_workload_percent: float = Field(0.0, description="Aggregate station capacity utilization percentage")
    emergency_stops_active: int = Field(0, description="Active emergency stop halts")


class SupervisorWorkerItem(AMAPBaseModel):
    """Worker summary item for supervisor live telemetry table."""
    worker_profile_id: UUID
    user_id: UUID
    full_name: str
    email: str
    status: str = Field(..., description="AVAILABLE | WORKING | PAUSED | ASSISTANCE_REQUESTED | COMPLETED | OFFLINE")
    current_task_id: Optional[UUID] = None
    current_task_name: Optional[str] = None
    current_assignment_id: Optional[UUID] = None
    progress_percent: float = 0.0
    current_step_title: Optional[str] = None
    current_step_number: Optional[int] = None
    total_steps: Optional[int] = None
    interaction_mode: str = "multimodal"
    interaction_health: Dict[str, bool] = Field(
        default_factory=lambda: {"gesture_ready": True, "voice_ready": True, "multimodal_ready": True}
    )
    active_session_id: Optional[UUID] = None
    session_duration_seconds: int = 0
    has_open_assistance: bool = False
    is_emergency_stop: bool = False
    is_online: bool = Field(False, description="Worker workstation heartbeat is fresh")
    last_activity_at: Optional[datetime] = None
    last_action_description: Optional[str] = Field(None, description="Most recent executed action name/type")


class SupervisorWorkerDetail(SupervisorWorkerItem):
    """Deep-dive worker detail view."""
    step_details: List[Dict[str, Any]] = Field(default_factory=list)
    recent_assistance_requests: List[Dict[str, Any]] = Field(default_factory=list)
    recent_task_assignments: List[Dict[str, Any]] = Field(default_factory=list)


class TaskAssignmentPayload(StrictInputModel):
    """Payload for supervisor assigning a task to an eligible worker."""
    task_id: UUID = Field(..., description="UUID of task to assign")
    worker_profile_id: UUID = Field(..., description="UUID of worker profile to assign task to")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional supervisor instruction notes")


class TaskReassignmentPayload(StrictInputModel):
    """Payload for supervisor reassigning a task assignment to another worker."""
    new_worker_profile_id: UUID = Field(..., description="UUID of target worker profile")
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for reassignment")


class AssistanceResponsePayload(StrictInputModel):
    """Payload for supervisor responding to an assistance request with guidance."""
    guidance_message: str = Field(..., min_length=1, max_length=1000, description="Supervisor guidance message")
    resolution_action: Optional[str] = Field(None, max_length=255, description="Action taken or suggested to worker")


class AssistanceResolvePayload(StrictInputModel):
    """Payload for supervisor resolving an assistance request."""
    resolution_notes: Optional[str] = Field(None, max_length=1000, description="Final resolution notes")


class SupervisorAnalytics(AMAPBaseModel):
    """Operational support and performance analytics for supervisor organization."""
    tasks_assigned_count: int = 0
    tasks_completed_count: int = 0
    tasks_in_progress_count: int = 0
    average_task_duration_minutes: float = 0.0
    workflow_completion_rate: float = 0.0
    total_assistance_requests: int = 0
    resolved_assistance_requests: int = 0
    average_resolution_time_minutes: float = 0.0
    emergency_stops_count: int = 0


class SupervisorAuditEvent(AMAPBaseModel):
    """Audit timeline item for supervisor dashboard."""
    id: UUID
    event_type: str
    actor_id: Optional[UUID] = None
    actor_name: str = "System"
    actor_email: Optional[str] = None
    resource_type: str
    resource_id: Optional[UUID] = None
    event_data: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
