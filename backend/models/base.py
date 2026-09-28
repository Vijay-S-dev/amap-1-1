"""
Base schemas and domain enumerations for AMAP.

Provides common Pydantic base configurations, strict field parsing,
and enumeration types aligned with PostgreSQL check constraints.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict


class EntityStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class WorkSessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InteractionMode(str, Enum):
    GESTURE = "gesture"
    VOICE = "voice"
    UI = "ui"
    OTHER = "other"


class ActionCategory(str, Enum):
    GENERAL = "general"
    NAVIGATION = "navigation"
    WORKFLOW = "workflow"
    TASK = "task"
    ASSISTANCE = "assistance"
    SYSTEM = "system"
    UI_INTERACTION = "ui_interaction"


class AssistanceStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class AssistancePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AMAPBaseModel(BaseModel):
    """
    Base model for all AMAP schemas.
    Configured for ORM compatibility and strict typing.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
    )


class StrictInputModel(AMAPBaseModel):
    """
    Base model for API input payloads.
    Forbids arbitrary extra fields to prevent mass-assignment attacks (Security Rule #15).
    """
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
    )
