"""
Enterprise Organization Domain Schemas for AMAP (§ 1, § 2, § 3, § 7, § 9, § 10, § 16, § 21).

Defines strict input/output models for:
- Organization Profile & Settings
- Departments CRUD
- Supervisor Rosters & Invitations
- Worker Rosters, Lifecycle States & Invitations
- Enterprise Workflow & Task Template Management
- Organization Dashboard KPIs, Assistance Overview, Analytics & Audit Stream
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus


# =====================================================================
# 1. Organization Profile & Settings
# =====================================================================

class OrganizationProfileRead(AMAPBaseModel):
    id: UUID
    name: str
    organization_type: str = "industrial_manufacturing"
    industry: str = "Automotive & Aerospace Assembly"
    location: Optional[str] = "Main Operations Facility"
    contact_email: Optional[str] = None
    status: str
    default_language: str = "en"
    supported_languages: List[str] = Field(default_factory=lambda: ["en", "es", "ta", "hi", "de"])
    accessibility_defaults: Dict[str, Any] = Field(
        default_factory=lambda: {
            "default_dwell_time_ms": 500,
            "high_contrast_default": False,
            "min_target_size_px": 48,
            "voice_confirmation_default": False,
        }
    )
    created_at: datetime
    updated_at: datetime


class OrganizationProfileUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    organization_type: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    default_language: Optional[str] = Field(None, max_length=10)
    supported_languages: Optional[List[str]] = None
    accessibility_defaults: Optional[Dict[str, Any]] = None


# =====================================================================
# 2. Departments
# =====================================================================

class DepartmentItem(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    status: str
    supervisor_count: int = 0
    worker_count: int = 0
    active_tasks_count: int = 0
    created_at: datetime
    updated_at: datetime


class DepartmentDetail(DepartmentItem):
    supervisors: List[Dict[str, Any]] = Field(default_factory=list)
    workers: List[Dict[str, Any]] = Field(default_factory=list)


class DepartmentCreatePayload(StrictInputModel):
    name: str = Field(..., min_length=1, max_length=255, description="Department name")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class DepartmentUpdatePayload(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[EntityStatus] = None


# =====================================================================
# 3. Supervisors
# =====================================================================

class SupervisorItem(AMAPBaseModel):
    user_id: UUID
    organization_id: UUID
    full_name: str
    email: str
    department_id: Optional[UUID] = None
    department_name: Optional[str] = "Unassigned"
    status: str  # active | invited | suspended
    assigned_workers_count: int = 0
    created_at: datetime


class SupervisorInvitePayload(StrictInputModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    department_id: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=500)


class SupervisorUpdatePayload(StrictInputModel):
    department_id: Optional[UUID] = None
    status: Optional[str] = None  # active | suspended


# =====================================================================
# 4. Workers & Lifecycle States (§ 10, § 11)
# =====================================================================

class EnterpriseWorkerItem(AMAPBaseModel):
    worker_profile_id: UUID
    user_id: UUID
    organization_id: UUID
    full_name: str
    email: str
    badge_number: Optional[str] = None
    department_id: Optional[UUID] = None
    department_name: Optional[str] = "Unassigned"
    supervisor_name: Optional[str] = "Unassigned"
    status: str  # INVITED | ONBOARDING | READY | WORKING | PAUSED | ASSISTANCE_REQUESTED | OFFLINE | DEACTIVATED
    interaction_mode: str = "multimodal"
    training_completed: bool = False
    current_task_name: Optional[str] = None
    created_at: datetime


class WorkerInvitePayload(StrictInputModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    badge_number: Optional[str] = Field(None, max_length=50)
    department_id: Optional[UUID] = None
    preferred_modality: Optional[str] = "multimodal"


class WorkerAssignmentPayload(StrictInputModel):
    department_id: Optional[UUID] = None
    supervisor_user_id: Optional[UUID] = None


# =====================================================================
# 5. Workflows & Task Templates (§ 14, § 16)
# =====================================================================

class WorkflowStepItem(AMAPBaseModel):
    step_number: int
    title: str
    instruction: str
    is_safety_critical: bool = False
    expected_duration_seconds: int = 120
    required_intent: Optional[str] = None


class WorkflowTemplate(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    version: int = 1
    status: str = "active"
    step_count: int = 0
    estimated_duration_minutes: float = 15.0
    steps: List[WorkflowStepItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowCreatePayload(StrictInputModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    department_id: Optional[UUID] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_duration_minutes: Optional[float] = 15.0


class WorkflowUpdatePayload(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    department_id: Optional[UUID] = None
    status: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None


# =====================================================================
# 6. Organization Dashboard & Operational Analytics (§ 5, § 21, § 22)
# =====================================================================

class OrganizationDashboardKPIs(AMAPBaseModel):
    organization_id: UUID
    organization_name: str
    total_workers_count: int
    active_workers_count: int
    available_workers_count: int
    supervisors_count: int
    departments_count: int
    active_tasks_count: int
    completed_tasks_count: int
    pending_tasks_count: int
    open_assistance_requests_count: int
    emergency_events_count: int
    current_line_utilization_percent: float


class OrganizationAnalyticsSummary(AMAPBaseModel):
    organization_id: UUID
    total_workers: int
    active_workers: int
    tasks_completed_count: int
    tasks_in_progress_count: int
    average_task_duration_minutes: float
    workflow_completion_rate: float
    total_assistance_requests: int
    average_resolution_time_minutes: float
    emergency_stops_count: int
    gesture_ready_workers_count: int
    voice_ready_workers_count: int
    multimodal_ready_workers_count: int
    workers_needing_training_count: int


class OrganizationAuditEventItem(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    actor_name: str
    actor_role: str
    event_type: str
    resource_type: str
    resource_id: Optional[UUID] = None
    occurred_at: datetime
    event_data: Dict[str, Any] = Field(default_factory=dict)
