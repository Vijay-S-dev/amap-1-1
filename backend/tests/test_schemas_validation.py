"""
Unit tests for Pydantic domain models and server-side validation schemas.
"""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from models.base import (
    EntityStatus,
    TaskStatus,
    WorkSessionStatus,
    InteractionMode,
    ActionCategory,
    AssistanceStatus,
    AssistancePriority,
)
from models.auth import (
    LoginRequest,
    TokenResponse,
    TokenPayload,
    AuthenticatedUserContext,
)
from models.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationRead,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentRead,
)
from models.user import (
    UserCreate,
    UserUpdate,
    UserPasswordUpdate,
    UserRead,
    UserInDB,
    RoleRead,
    PermissionRead,
    UserRoleAssignmentCreate,
    UserRoleAssignmentRead,
    RolePermissionAssignmentCreate,
    RolePermissionAssignmentRead,
    UserDepartmentAssignmentCreate,
    UserDepartmentAssignmentRead,
)
from models.worker import (
    WorkerProfileCreate,
    WorkerProfileRead,
    WorkerJobAssignmentCreate,
    WorkerJobAssignmentRead,
    WorkerTaskAssignmentCreate,
    WorkerTaskAssignmentUpdate,
    WorkerTaskAssignmentRead,
    WorkerCapabilityProfileCreate,
    WorkerCapabilityProfileUpdate,
    WorkerCapabilityProfileRead,
    WorkerPersonalizationCreate,
    WorkerPersonalizationUpdate,
    WorkerPersonalizationRead,
    PersonalizationHistoryCreate,
    PersonalizationHistoryRead,
)
from models.job import (
    JobCreate,
    JobUpdate,
    JobRead,
    ResponsibilityCreate,
    ResponsibilityUpdate,
    ResponsibilityRead,
)
from models.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowRead,
    WorkflowStepCreate,
    WorkflowStepUpdate,
    WorkflowStepRead,
    WorkflowAssignmentCreate,
    WorkflowAssignmentUpdate,
    WorkflowAssignmentRead,
    WorkflowStepExecutionCreate,
    WorkflowStepExecutionUpdate,
    WorkflowStepExecutionRead,
    WorkflowStepResponsibilityCreate,
    WorkflowStepResponsibilityRead,
    WorkflowStepActionCreate,
    WorkflowStepActionRead,
)
from models.task import (
    TaskCreate,
    TaskUpdate,
    TaskRead,
    TaskResponsibilityCreate,
    TaskResponsibilityRead,
    TaskWorkflowCreate,
    TaskWorkflowRead,
    TaskResultCreate,
    TaskResultRead,
    TaskActionCreate,
    TaskActionRead,
)
from models.action import (
    ActionCreate,
    ActionUpdate,
    ActionRead,
    ActionRequirementCreate,
    ActionRequirementUpdate,
    ActionRequirementRead,
    ActionExecutionRequest,
    ActionExecutionResponse,
)
from models.interaction import (
    InteractionConfigurationCreate,
    InteractionConfigurationUpdate,
    InteractionConfigurationRead,
    GestureConfigurationCreate,
    GestureConfigurationUpdate,
    GestureConfigurationRead,
    VoiceConfigurationCreate,
    VoiceConfigurationUpdate,
    VoiceConfigurationRead,
    InteractionEventCreate,
    InteractionEventRead,
    MultimodalIntentPayload,
    MultimodalProcessingResult,
)
from models.session import (
    WorkSessionCreate,
    WorkSessionUpdate,
    WorkSessionRead,
    ExecutionEventCreate,
    ExecutionEventRead,
)
from models.assistance import (
    NotificationStatus,
    AssistanceRequestCreate,
    AssistanceRequestUpdate,
    AssistanceRequestRead,
    NotificationCreate,
    NotificationUpdate,
    NotificationRead,
)
from models.audit import (
    AuditEventCreate,
    AuditEventRead,
)


# =====================================================================
# Auth Schemas Tests
# =====================================================================

def test_login_request_valid():
    req = LoginRequest(
        organization_id=uuid.uuid4(),
        email="worker@amap.org",
        password="SecurePassword123!",
    )
    assert req.email == "worker@amap.org"
    assert req.password == "SecurePassword123!"


def test_login_request_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(
            organization_id=uuid.uuid4(),
            email="invalid-email-string",
            password="SecurePassword123!",
        )


def test_login_request_short_password():
    with pytest.raises(ValidationError):
        LoginRequest(
            organization_id=uuid.uuid4(),
            email="worker@amap.org",
            password="short",
        )


def test_login_request_forbids_extra_fields():
    with pytest.raises(ValidationError):
        LoginRequest(
            organization_id=uuid.uuid4(),
            email="worker@amap.org",
            password="SecurePassword123!",
            is_admin=True,  # Extra forbidden field
        )


def test_token_response_and_payload():
    resp = TokenResponse(access_token="jwt.token.here", expires_in=3600)
    assert resp.access_token == "jwt.token.here"
    assert resp.token_type == "bearer"

    payload = TokenPayload(
        sub=str(uuid.uuid4()),
        organization_id=str(uuid.uuid4()),
        email="worker@amap.org",
        roles=["worker"],
        permissions=["tasks:read"],
    )
    assert payload.roles == ["worker"]


def test_authenticated_user_context():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    context = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Alex Worker",
        status="active",
        roles=["worker"],
        permissions=["action:execute"],
    )
    assert context.user_id == user_id
    assert context.worker_profile_id is None


# =====================================================================
# Organization & Department Schemas Tests
# =====================================================================

def test_organization_create_valid():
    org = OrganizationCreate(name="Acme Logistics")
    assert org.name == "Acme Logistics"
    assert org.status == EntityStatus.ACTIVE


def test_organization_create_forbids_extra_field():
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Acme", extra_field="forbidden")


def test_department_create_and_read():
    org_id = uuid.uuid4()
    dept = DepartmentCreate(organization_id=org_id, name="Warehouse Operations")
    assert dept.organization_id == org_id

    read_dept = DepartmentRead(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Warehouse Operations",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert read_dept.name == "Warehouse Operations"


# =====================================================================
# User & Worker Schemas Tests
# =====================================================================

def test_user_create_validation():
    org_id = uuid.uuid4()
    user = UserCreate(
        organization_id=org_id,
        email="test@amap.org",
        full_name="Jane Doe",
        password="StrongPassword123!",
    )
    assert user.full_name == "Jane Doe"


def test_user_read_does_not_contain_password_hash():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user_read = UserRead(
        id=user_id,
        organization_id=org_id,
        email="test@amap.org",
        full_name="Jane Doe",
        status="active",
        created_at=now,
        updated_at=now,
    )
    assert not hasattr(user_read, "password_hash")

    user_db = UserInDB(
        id=user_id,
        organization_id=org_id,
        email="test@amap.org",
        full_name="Jane Doe",
        status="active",
        password_hash="hashed_secret",
        created_at=now,
        updated_at=now,
    )
    assert user_db.password_hash == "hashed_secret"


def test_worker_profile_and_capability():
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    wp = WorkerProfileRead(
        id=worker_id,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    assert wp.user_id == user_id

    cap = WorkerCapabilityProfileCreate(
        worker_profile_id=worker_id,
        capability_data={"preferred_modality": "gesture", "reach_range": "medium"},
    )
    assert cap.capability_data["preferred_modality"] == "gesture"


# =====================================================================
# Workflow & Step Schemas Tests
# =====================================================================

def test_workflow_step_order_positive():
    wf_id = uuid.uuid4()
    step = WorkflowStepCreate(
        workflow_id=wf_id,
        step_order=1,
        name="Pick Item",
    )
    assert step.step_order == 1

    with pytest.raises(ValidationError):
        WorkflowStepCreate(
            workflow_id=wf_id,
            step_order=0,  # Invalid: must be > 0
            name="Invalid Step",
        )


# =====================================================================
# Task Schemas Tests
# =====================================================================

def test_task_create_and_result():
    org_id = uuid.uuid4()
    task = TaskCreate(
        organization_id=org_id,
        name="Scan Barcode",
        description="Scan pallet barcode",
    )
    assert task.status == TaskStatus.ACTIVE

    assignment_id = uuid.uuid4()
    result = TaskResultCreate(
        worker_task_assignment_id=assignment_id,
        result_data={"scanned_code": "123456789"},
    )
    assert result.result_data["scanned_code"] == "123456789"


# =====================================================================
# Action & Execution Schemas Tests
# =====================================================================

def test_action_execution_request_and_response():
    req = ActionExecutionRequest(
        action_name="confirm_step",
        parameters={"step_number": 2},
    )
    assert req.action_name == "confirm_step"

    resp = ActionExecutionResponse(
        success=True,
        action_id=uuid.uuid4(),
        action_name="confirm_step",
        executed_at=datetime.now(timezone.utc),
        feedback_message="Step 2 confirmed successfully",
    )
    assert resp.success is True
    assert resp.feedback_message == "Step 2 confirmed successfully"


# =====================================================================
# Interaction & Multimodal Schemas Tests
# =====================================================================

def test_interaction_event_confidence_bounds():
    org_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    event = InteractionEventCreate(
        organization_id=org_id,
        worker_profile_id=worker_id,
        interaction_mode=InteractionMode.GESTURE,
        event_type="swipe_right",
        confidence=0.95,
    )
    assert event.confidence == 0.95

    # Negative confidence must fail
    with pytest.raises(ValidationError):
        InteractionEventCreate(
            organization_id=org_id,
            worker_profile_id=worker_id,
            interaction_mode=InteractionMode.GESTURE,
            event_type="swipe_right",
            confidence=-0.1,
        )

    # Confidence > 1.0 must fail
    with pytest.raises(ValidationError):
        InteractionEventCreate(
            organization_id=org_id,
            worker_profile_id=worker_id,
            interaction_mode=InteractionMode.GESTURE,
            event_type="swipe_right",
            confidence=1.05,
        )


def test_multimodal_intent_payload_and_result():
    intent = MultimodalIntentPayload(
        mode=InteractionMode.VOICE,
        raw_intent="next step",
        confidence=0.88,
    )
    assert intent.mode == InteractionMode.VOICE

    result = MultimodalProcessingResult(
        recognized=True,
        action_name="next_step",
        confidence=0.88,
        requires_confirmation=False,
    )
    assert result.action_name == "next_step"


# =====================================================================
# Work Session & Execution Event Schemas Tests
# =====================================================================

def test_work_session_read_dates_validator():
    worker_id = uuid.uuid4()
    t1 = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 20, 11, 0, 0, tzinfo=timezone.utc)

    # Valid: ended_at >= started_at
    session = WorkSessionRead(
        id=uuid.uuid4(),
        worker_profile_id=worker_id,
        status="completed",
        started_at=t1,
        ended_at=t2,
        created_at=t1,
        updated_at=t2,
    )
    assert session.ended_at == t2

    # Invalid: ended_at < started_at
    with pytest.raises(ValidationError):
        WorkSessionRead(
            id=uuid.uuid4(),
            worker_profile_id=worker_id,
            status="completed",
            started_at=t2,
            ended_at=t1,
            created_at=t1,
            updated_at=t2,
        )


# =====================================================================
# Assistance & Notification Schemas Tests
# =====================================================================

def test_assistance_request_dates_validator():
    org_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    t1 = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 20, 10, 30, 0, tzinfo=timezone.utc)
    t_invalid = datetime(2026, 8, 20, 9, 0, 0, tzinfo=timezone.utc)

    req = AssistanceRequestRead(
        id=uuid.uuid4(),
        organization_id=org_id,
        worker_profile_id=worker_id,
        status="acknowledged",
        priority="normal",
        request_data={},
        requested_at=t1,
        acknowledged_at=t2,
        created_at=t1,
        updated_at=t2,
    )
    assert req.acknowledged_at == t2

    # Acknowledged before requested must fail
    with pytest.raises(ValidationError):
        AssistanceRequestRead(
            id=uuid.uuid4(),
            organization_id=org_id,
            worker_profile_id=worker_id,
            status="acknowledged",
            priority="normal",
            request_data={},
            requested_at=t1,
            acknowledged_at=t_invalid,
            created_at=t1,
            updated_at=t2,
        )


def test_notification_dates_validator():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    t1 = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 20, 10, 5, 0, tzinfo=timezone.utc)
    t_invalid = datetime(2026, 8, 20, 9, 50, 0, tzinfo=timezone.utc)

    notif = NotificationRead(
        id=uuid.uuid4(),
        organization_id=org_id,
        recipient_user_id=user_id,
        notification_type="task_assigned",
        title="New Task",
        message="You have a new task",
        notification_data={},
        status="read",
        created_at=t1,
        read_at=t2,
    )
    assert notif.status == "read"

    with pytest.raises(ValidationError):
        NotificationRead(
            id=uuid.uuid4(),
            organization_id=org_id,
            recipient_user_id=user_id,
            notification_type="task_assigned",
            title="New Task",
            message="You have a new task",
            notification_data={},
            status="read",
            created_at=t1,
            read_at=t_invalid,
        )


# =====================================================================
# Audit Event Schemas Tests
# =====================================================================

def test_audit_event_create_and_read():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    audit = AuditEventCreate(
        organization_id=org_id,
        actor_user_id=user_id,
        event_type="user.login",
        resource_type="user",
        resource_id=user_id,
        event_data={"ip": "127.0.0.1"},
    )
    assert audit.event_type == "user.login"
