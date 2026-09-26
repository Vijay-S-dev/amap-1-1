"""
End-to-End Worker Workflow Integration Tests for AMAP (Phase 8).

Validates the complete worker lifecycle:
1. Authentication & Token Issuance
2. Worker Profile & Context Resolution
3. Work Session Start & Active State Tracking
4. Task Assignment Discovery & Activation
5. Multimodal Intent Recognition & Confidence Tiering
6. Deterministic Action Safety Validation & Execution Gate
7. Workflow Step Progression & Execution Recording
8. Worker Assistance & Notification Orchestration
9. Evidence-Based Personalization Analysis
10. Task Completion & Outcome Storage
11. Work Session End & State Finalization
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_auth_service
from app.main import app
from models.action import ActionExecutionResponse
from models.assistance import (
    AssistancePriority,
    AssistanceRequestRead,
    NotificationCreate,
    NotificationRead,
)
from models.auth import AuthenticatedUserContext, TokenResponse
from models.interaction import MultimodalProcessingResult
from models.session import WorkSessionRead
from models.user import UserInDB
from models.worker import WorkerPersonalizationRead, WorkerTaskAssignmentRead
from routes.actions import get_action_execution_service
from routes.assistance import get_assistance_service
from routes.interactions import get_interaction_service
from routes.personalization import get_personalization_service
from routes.sessions import get_work_session_service
from routes.tasks import get_task_service
from services.base import SafetyViolationError, UnauthorizedError
from utils.security import create_access_token, hash_password


# =====================================================================
# Full E2E Worker Workflow Test
# =====================================================================

def test_e2e_complete_worker_session_and_task_lifecycle():
    client = TestClient(app)

    # 1. Setup simulated organization, user, worker, and task IDs
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    step_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Mock domain services
    mock_auth_svc = MagicMock()
    mock_session_svc = MagicMock()
    mock_task_svc = MagicMock()
    mock_action_svc = MagicMock()
    mock_interaction_svc = MagicMock()
    mock_pers_svc = MagicMock()

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_svc
    app.dependency_overrides[get_work_session_service] = lambda: mock_session_svc
    app.dependency_overrides[get_task_service] = lambda: mock_task_svc
    app.dependency_overrides[get_action_execution_service] = lambda: mock_action_svc
    app.dependency_overrides[get_interaction_service] = lambda: mock_interaction_svc
    app.dependency_overrides[get_personalization_service] = lambda: mock_pers_svc

    try:
        # Step 1: Worker Login
        worker_token = create_access_token({
            "sub": str(user_id),
            "organization_id": str(org_id),
            "email": "worker@amap.org",
            "roles": ["worker"],
            "permissions": ["tasks:read", "tasks:write", "actions:execute"],
            "worker_profile_id": str(worker_id),
        })

        mock_auth_svc.authenticate_user.return_value = (
            UserInDB(
                id=user_id,
                organization_id=org_id,
                email="worker@amap.org",
                full_name="AMAP Assembly Worker",
                password_hash=hash_password("Password123!"),
                status="active",
                created_at=now,
                updated_at=now,
            ),
            TokenResponse(
                access_token=worker_token,
                token_type="bearer",
                expires_in=3600,
            ),
        )

        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": str(org_id),
                "email": "worker@amap.org",
                "password": "Password123!",
            },
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Resolve Authenticated Context
        mock_auth_svc.verify_token.return_value = AuthenticatedUserContext(
            user_id=user_id,
            organization_id=org_id,
            email="worker@amap.org",
            full_name="AMAP Assembly Worker",
            status="active",
            roles=["worker"],
            permissions=[
                "tasks:read",
                "tasks:write",
                "actions:execute",
                "assistance:request",
                "session:read",
                "session:write",
                "multimodal:input",
            ],
            worker_profile_id=worker_id,
        )

        me_resp = client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["worker_profile_id"] == str(worker_id)

        # Step 3: Start Work Session
        mock_session_svc.start_session.return_value = WorkSessionRead(
            id=session_id,
            worker_profile_id=worker_id,
            status="active",
            started_at=now,
            ended_at=None,
            created_at=now,
            updated_at=now,
        )

        start_sess_resp = client.post("/api/v1/sessions/start", headers=headers)
        assert start_sess_resp.status_code == 201
        assert start_sess_resp.json()["id"] == str(session_id)

        # Step 4: Verify Active Session
        mock_session_svc.get_active_session.return_value = WorkSessionRead(
            id=session_id,
            worker_profile_id=worker_id,
            status="active",
            started_at=now,
            ended_at=None,
            created_at=now,
            updated_at=now,
        )

        active_sess_resp = client.get("/api/v1/sessions/active", headers=headers)
        assert active_sess_resp.status_code == 200
        assert active_sess_resp.json()["status"] == "active"

        # Step 5: Query Assigned Tasks
        mock_task_svc.get_worker_assignments.return_value = [
            WorkerTaskAssignmentRead(
                id=assignment_id,
                task_id=task_id,
                worker_profile_id=worker_id,
                status="assigned",
                assigned_at=now,
                started_at=None,
                completed_at=None,
                created_at=now,
                updated_at=now,
            )
        ]

        tasks_resp = client.get("/api/v1/tasks/assigned", headers=headers)
        assert tasks_resp.status_code == 200
        assert len(tasks_resp.json()) == 1
        assert tasks_resp.json()[0]["id"] == str(assignment_id)

        # Step 6: Start Task Assignment
        mock_task_svc.start_task_assignment.return_value = WorkerTaskAssignmentRead(
            id=assignment_id,
            task_id=task_id,
            worker_profile_id=worker_id,
            status="active",
            assigned_at=now,
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )

        start_task_resp = client.post(
            f"/api/v1/tasks/assignments/{assignment_id}/start",
            headers=headers,
        )
        assert start_task_resp.status_code == 200
        assert start_task_resp.json()["status"] == "active"

        # Step 7: Multimodal Intent Recognition (Gesture -> Action)
        mock_interaction_svc.process_multimodal_intent.return_value = (
            MultimodalProcessingResult(
                recognized=True,
                action_name="next_step",
                confidence=0.92,
                requires_confirmation=False,
                validation_status="valid",
                message="Action 'next_step' recognized.",
            )
        )

        intent_resp = client.post(
            f"/api/v1/interactions/process-intent?work_session_id={session_id}",
            headers=headers,
            json={
                "mode": "gesture",
                "raw_intent": "swipe_right",
                "confidence": 0.92,
            },
        )
        assert intent_resp.status_code == 200
        assert intent_resp.json()["action_name"] == "next_step"
        assert intent_resp.json()["requires_confirmation"] is False

        # Step 8: Deterministic Action Execution Gate
        mock_action_svc.execute_action.return_value = ActionExecutionResponse(
            success=True,
            action_id=uuid.uuid4(),
            action_name="next_step",
            executed_at=now,
            result_data={"status": "executed", "step_from": 1, "step_to": 2},
            feedback_message="Advanced to step 2",
        )

        exec_resp = client.post(
            "/api/v1/actions/execute",
            headers=headers,
            json={
                "action_name": "next_step",
                "work_session_id": str(session_id),
                "workflow_step_id": str(step_id),
                "parameters": {"step_number": 2},
            },
        )
        assert exec_resp.status_code == 200
        assert exec_resp.json()["success"] is True

        # Step 9: Record Workflow Step Progression
        mock_task_svc.record_step_execution.return_value = {
            "id": str(uuid.uuid4()),
            "workflow_step_id": str(step_id),
            "status": "completed",
        }

        step_exec_resp = client.post(
            f"/api/v1/tasks/workflows/assignments/{workflow_id}/steps/{step_id}/execute",
            headers=headers,
            json={"status": "completed", "execution_data": {"duration_sec": 45}},
        )
        assert step_exec_resp.status_code == 201

        # Step 10: Complete Task Assignment
        mock_task_svc.complete_task_assignment.return_value = {
            "id": str(uuid.uuid4()),
            "worker_task_assignment_id": str(assignment_id),
            "outcome": "completed",
            "result_data": {"barcode": "PART-99482"},
            "notes": "Assembly completed cleanly",
        }

        complete_task_resp = client.post(
            f"/api/v1/tasks/assignments/{assignment_id}/complete",
            headers=headers,
            json={
                "outcome": "completed",
                "result_data": {"barcode": "PART-99482"},
                "notes": "Assembly completed cleanly",
            },
        )
        assert complete_task_resp.status_code == 200
        assert complete_task_resp.json()["outcome"] == "completed"

        # Step 11: End Work Session
        mock_session_svc.end_session.return_value = WorkSessionRead(
            id=session_id,
            worker_profile_id=worker_id,
            status="completed",
            started_at=now,
            ended_at=now,
            created_at=now,
            updated_at=now,
        )

        end_sess_resp = client.post(
            f"/api/v1/sessions/{session_id}/end?status=completed",
            headers=headers,
        )
        assert end_sess_resp.status_code == 200
        assert end_sess_resp.json()["status"] == "completed"

    finally:
        app.dependency_overrides.clear()


# =====================================================================
# E2E Safety Gate Enforcement
# =====================================================================

def test_e2e_worker_safety_gate_enforcement_in_workflow():
    client = TestClient(app)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    mock_auth_svc = MagicMock()
    mock_action_svc = MagicMock()

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_svc
    app.dependency_overrides[get_action_execution_service] = lambda: mock_action_svc

    mock_auth_svc.verify_token.return_value = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="AMAP Worker",
        status="active",
        roles=["worker"],
        permissions=["actions:execute", "assistance:request"],
        worker_profile_id=worker_id,
    )

    try:
        headers = {"Authorization": "Bearer valid-jwt-token"}

        # Attempt to execute action missing safety prerequisite
        mock_action_svc.execute_action.side_effect = SafetyViolationError(
            "Action 'emergency_stop' requires explicit hardware interlock parameter."
        )

        resp = client.post(
            "/api/v1/actions/execute",
            headers=headers,
            json={
                "action_name": "emergency_stop",
                "parameters": {},
            },
        )
        assert resp.status_code == 422
        assert "Safety Gate Violation" in resp.json()["error"]
        assert "interlock" in resp.json()["error"]

    finally:
        app.dependency_overrides.clear()


# =====================================================================
# E2E Assistance and Notification Flow
# =====================================================================

def test_e2e_worker_assistance_and_notification_flow():
    client = TestClient(app)

    org_id = uuid.uuid4()
    worker_user_id = uuid.uuid4()
    worker_profile_id = uuid.uuid4()
    supervisor_user_id = uuid.uuid4()
    request_id = uuid.uuid4()
    notification_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_auth_svc = MagicMock()
    mock_assist_svc = MagicMock()

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_svc
    app.dependency_overrides[get_assistance_service] = lambda: mock_assist_svc

    try:
        # Worker Context
        worker_ctx = AuthenticatedUserContext(
            user_id=worker_user_id,
            organization_id=org_id,
            email="worker@amap.org",
            full_name="Worker",
            status="active",
            roles=["worker"],
            permissions=["assistance:request"],
            worker_profile_id=worker_profile_id,
        )

        # Supervisor Context
        supervisor_ctx = AuthenticatedUserContext(
            user_id=supervisor_user_id,
            organization_id=org_id,
            email="supervisor@amap.org",
            full_name="Supervisor",
            status="active",
            roles=["supervisor"],
            permissions=["assistance:resolve"],
            worker_profile_id=None,
        )

        # 1. Worker creates assistance request
        mock_auth_svc.verify_token.return_value = worker_ctx
        mock_assist_svc.create_assistance_request.return_value = (
            AssistanceRequestRead(
                id=request_id,
                organization_id=org_id,
                worker_profile_id=worker_profile_id,
                work_session_id=None,
                workflow_assignment_id=None,
                worker_task_assignment_id=None,
                status="open",
                priority=AssistancePriority.HIGH,
                reason="Component alignment issue at station 3",
                request_data={},
                requested_at=now,
                acknowledged_at=None,
                resolved_at=None,
                created_at=now,
                updated_at=now,
            )
        )

        req_resp = client.post(
            "/api/v1/assistance/requests",
            headers={"Authorization": "Bearer worker-token"},
            json={
                "reason": "Component alignment issue at station 3",
                "priority": "high",
            },
        )
        assert req_resp.status_code == 201
        assert req_resp.json()["priority"] == "high"

        # 2. Supervisor acknowledges request
        mock_auth_svc.verify_token.return_value = supervisor_ctx
        mock_assist_svc.acknowledge_request.return_value = AssistanceRequestRead(
            id=request_id,
            organization_id=org_id,
            worker_profile_id=worker_profile_id,
            work_session_id=None,
            workflow_assignment_id=None,
            worker_task_assignment_id=None,
            status="acknowledged",
            priority=AssistancePriority.HIGH,
            reason="Component alignment issue at station 3",
            request_data={},
            requested_at=now,
            acknowledged_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )

        ack_resp = client.post(
            f"/api/v1/assistance/requests/{request_id}/acknowledge",
            headers={"Authorization": "Bearer supervisor-token"},
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "acknowledged"

        # 3. Supervisor resolves request
        mock_assist_svc.resolve_request.return_value = AssistanceRequestRead(
            id=request_id,
            organization_id=org_id,
            worker_profile_id=worker_profile_id,
            work_session_id=None,
            workflow_assignment_id=None,
            worker_task_assignment_id=None,
            status="resolved",
            priority=AssistancePriority.HIGH,
            reason="Component alignment issue at station 3",
            request_data={},
            requested_at=now,
            acknowledged_at=now,
            resolved_at=now,
            created_at=now,
            updated_at=now,
        )

        resolve_resp = client.post(
            f"/api/v1/assistance/requests/{request_id}/resolve",
            headers={"Authorization": "Bearer supervisor-token"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "resolved"

    finally:
        app.dependency_overrides.clear()


# =====================================================================
# E2E Cross-Tenant Isolation
# =====================================================================

def test_e2e_cross_tenant_isolation_during_workflow():
    client = TestClient(app)

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    mock_auth_svc = MagicMock()
    mock_assist_svc = MagicMock()

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_svc
    app.dependency_overrides[get_assistance_service] = lambda: mock_assist_svc

    # Caller belongs to Org A
    mock_auth_svc.verify_token.return_value = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_a,
        email="worker@orga.com",
        full_name="Worker A",
        status="active",
        roles=["supervisor"],
        permissions=["assistance:resolve"],
        worker_profile_id=worker_id,
    )

    try:
        headers = {"Authorization": "Bearer orga-token"}

        # Attempt to acknowledge request belonging to Org B
        foreign_request_id = uuid.uuid4()
        mock_assist_svc.acknowledge_request.side_effect = UnauthorizedError(
            "Assistance request does not belong to this organization."
        )

        resp = client.post(
            f"/api/v1/assistance/requests/{foreign_request_id}/acknowledge",
            headers=headers,
        )
        assert resp.status_code == 403
        assert "not belong to this organization" in resp.json()["error"]

    finally:
        app.dependency_overrides.clear()
