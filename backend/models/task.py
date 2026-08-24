"""
Task, Task Workflow, and Result schemas for AMAP.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, TaskStatus


class TaskCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: Optional[str] = Field(None, max_length=2000, description="Task description")
    status: TaskStatus = Field(default=TaskStatus.ACTIVE, description="Task status")


class TaskUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[TaskStatus] = None


class TaskRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class TaskResponsibilityCreate(StrictInputModel):
    task_id: UUID
    responsibility_id: UUID


class TaskResponsibilityRead(AMAPBaseModel):
    id: UUID
    task_id: UUID
    responsibility_id: UUID
    created_at: datetime


class TaskWorkflowCreate(StrictInputModel):
    task_id: UUID
    workflow_id: UUID


class TaskWorkflowRead(AMAPBaseModel):
    id: UUID
    task_id: UUID
    workflow_id: UUID
    created_at: datetime


class TaskResultCreate(StrictInputModel):
    worker_task_assignment_id: UUID
    work_session_id: Optional[UUID] = None
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)
    result_data: Dict[str, Any] = Field(default_factory=dict)


class TaskResultRead(AMAPBaseModel):
    id: UUID
    worker_task_assignment_id: UUID
    work_session_id: Optional[UUID] = None
    status: str
    result_data: Dict[str, Any]
    completed_at: datetime
    created_at: datetime
    updated_at: datetime


class TaskActionCreate(StrictInputModel):
    task_id: UUID
    action_id: UUID


class TaskActionRead(AMAPBaseModel):
    id: UUID
    task_id: UUID
    action_id: UUID
    created_at: datetime
