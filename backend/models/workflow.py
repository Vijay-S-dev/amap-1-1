"""
Workflow, Workflow Step, and Execution schemas for AMAP.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus, TaskStatus


class WorkflowCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    description: Optional[str] = Field(None, max_length=2000, description="Workflow description")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Workflow status")


class WorkflowUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[EntityStatus] = None


class WorkflowRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class WorkflowStepCreate(StrictInputModel):
    workflow_id: UUID = Field(..., description="Workflow UUID")
    step_order: int = Field(..., gt=0, description="1-based step order sequence")
    name: str = Field(..., min_length=1, max_length=255, description="Step name")
    description: Optional[str] = Field(None, max_length=2000, description="Step description")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Step status")


class WorkflowStepUpdate(StrictInputModel):
    step_order: Optional[int] = Field(None, gt=0)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[EntityStatus] = None


class WorkflowStepRead(AMAPBaseModel):
    id: UUID
    workflow_id: UUID
    step_order: int
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class WorkflowAssignmentCreate(StrictInputModel):
    worker_profile_id: UUID
    workflow_id: UUID
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)


class WorkflowAssignmentUpdate(StrictInputModel):
    status: Optional[TaskStatus] = None


class WorkflowAssignmentRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    workflow_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class WorkflowStepExecutionCreate(StrictInputModel):
    workflow_assignment_id: UUID
    workflow_step_id: UUID
    work_session_id: Optional[UUID] = None
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)
    execution_data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStepExecutionUpdate(StrictInputModel):
    status: Optional[TaskStatus] = None
    execution_data: Optional[Dict[str, Any]] = None


class WorkflowStepExecutionRead(AMAPBaseModel):
    id: UUID
    workflow_assignment_id: UUID
    workflow_step_id: UUID
    work_session_id: Optional[UUID] = None
    status: str
    execution_data: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkflowStepResponsibilityCreate(StrictInputModel):
    workflow_step_id: UUID
    responsibility_id: UUID


class WorkflowStepResponsibilityRead(AMAPBaseModel):
    id: UUID
    workflow_step_id: UUID
    responsibility_id: UUID
    created_at: datetime


class WorkflowStepActionCreate(StrictInputModel):
    workflow_step_id: UUID
    action_id: UUID


class WorkflowStepActionRead(AMAPBaseModel):
    id: UUID
    workflow_step_id: UUID
    action_id: UUID
    created_at: datetime
