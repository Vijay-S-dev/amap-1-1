"""
Action, Action Requirement, and Action Execution schemas for AMAP.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, ActionCategory, EntityStatus


class ActionCreate(StrictInputModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unique action programmatic name")
    display_name: str = Field(..., min_length=1, max_length=255, description="Human readable name")
    description: Optional[str] = Field(None, max_length=2000, description="Description of the action")
    category: ActionCategory = Field(default=ActionCategory.GENERAL, description="Action category")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Action status")


class ActionUpdate(StrictInputModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[ActionCategory] = None
    status: Optional[EntityStatus] = None


class ActionRead(AMAPBaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    status: str
    created_at: datetime
    updated_at: datetime


class ActionRequirementCreate(StrictInputModel):
    action_id: UUID
    requirement_type: str = Field(..., min_length=1, max_length=100)
    requirement_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class ActionRequirementUpdate(StrictInputModel):
    requirement_type: Optional[str] = Field(None, min_length=1, max_length=100)
    requirement_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class ActionRequirementRead(AMAPBaseModel):
    id: UUID
    action_id: UUID
    requirement_type: str
    requirement_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class ActionExecutionRequest(StrictInputModel):
    """
    Client request to execute a deterministic action.
    Goes through server-side authorization and safety gates.
    """
    action_name: str = Field(..., min_length=1, max_length=100)
    work_session_id: Optional[UUID] = None
    workflow_step_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResponse(AMAPBaseModel):
    """
    Deterministic response from action execution engine.
    """
    success: bool
    action_id: UUID
    action_name: str
    executed_at: datetime
    result_data: Dict[str, Any] = Field(default_factory=dict)
    feedback_message: Optional[str] = None
