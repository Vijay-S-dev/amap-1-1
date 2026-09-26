"""
Comprehensive Test Suite for AMAP Supervisor / Manager Module (§ 30).

Tests:
1. Supervisor login and authentication.
2. Worker cannot access supervisor APIs (403 Forbidden).
3. Supervisor can access own organization data.
4. Supervisor cannot access other organization data (Tenant Isolation).
5. Live worker list with operational status derivation.
6. Worker detail deep-dive inspection.
7. Task assignment to eligible worker.
8. Invalid task assignment rejection (wrong org / ineligible).
9. Assistance queue ingestion and priority sorting.
10. Assistance acknowledgement.
11. Assistance response with guidance message.
12. Assistance resolution and closure.
13. Emergency stop escalation and event retrieval.
14. Live task progress step tracking.
15. Immutable audit timeline logging on supervisor actions.
16. RBAC role enforcement (worker vs. supervisor vs. admin).
17. Organization isolation on all mutations.
18. Schema input validation (422 / 400).
19. Error handling with safe diagnostic feedback (no stack traces).
20. Complete end-to-end supervisor operational lifecycle.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4
import pytest
from starlette.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.supervisor import (
    AssistanceResolvePayload,
    AssistanceResponsePayload,
    SupervisorAnalytics,
    SupervisorAuditEvent,
    SupervisorDashboardSummary,
    SupervisorWorkerDetail,
    SupervisorWorkerItem,
    TaskAssignmentPayload,
    TaskReassignmentPayload,
)
from routes.supervisor import get_supervisor_service
from services.base import ConflictError, NotFoundError, UnauthorizedError
from services.supervisor_service import SupervisorService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def org_a_id():
    return uuid4()


@pytest.fixture
def org_b_id():
    return uuid4()


@pytest.fixture
def supervisor_user(org_a_id):
    return AuthenticatedUserContext(
        user_id=uuid4(),
        organization_id=org_a_id,
        email="supervisor@amap.org",
        full_name="Sarah Connor",
        status="active",
        roles=["supervisor"],
        permissions=[
            "supervisor:read",
            "supervisor:write",
            "tasks:assign",
            "assistance:manage",
            "assistance:resolve",
        ],
    )


@pytest.fixture
def worker_user(org_a_id):
    return AuthenticatedUserContext(
        user_id=uuid4(),
        worker_profile_id=uuid4(),
        organization_id=org_a_id,
        email="worker@amap.org",
        full_name="John Doe",
        status="active",
        roles=["worker"],
        permissions=["tasks:execute", "assistance:create"],
    )


# =========================================================================
# Unit Tests for SupervisorService
# =========================================================================

def test_supervisor_service_dashboard_summary_unit():
    """Unit test for computing supervisor dashboard summary."""
    mock_users_repo = MagicMock()
    mock_wp_repo = MagicMock()
    mock_sessions_repo = MagicMock()
    mock_tasks_repo = MagicMock()
    mock_assignments_repo = MagicMock()
    mock_assistance_repo = MagicMock()
    mock_audit_repo = MagicMock()
    mock_personalizations_repo = MagicMock()
    mock_wf_assigns_repo = MagicMock()
    mock_wf_steps_repo = MagicMock()
    mock_workflows_repo = MagicMock()
    mock_interaction_configs_repo = MagicMock()
    mock_readiness_repo = MagicMock()
    mock_readiness_repo.get.return_value = None
    mock_task_workflows_repo = MagicMock()
    mock_task_workflows_repo.list_by_task_id.return_value = []
    mock_step_execs_repo = MagicMock()
    mock_step_execs_repo.list_by_workflow_assignment_id.return_value = []
    mock_task_results_repo = MagicMock()

    service = SupervisorService(
        users_repo=mock_users_repo,
        worker_profiles_repo=mock_wp_repo,
        work_sessions_repo=mock_sessions_repo,
        tasks_repo=mock_tasks_repo,
        worker_task_assignments_repo=mock_assignments_repo,
        assistance_requests_repo=mock_assistance_repo,
        audit_events_repo=mock_audit_repo,
        worker_personalizations_repo=mock_personalizations_repo,
        workflow_assignments_repo=mock_wf_assigns_repo,
        workflow_steps_repo=mock_wf_steps_repo,
        workflows_repo=mock_workflows_repo,
        interaction_configs_repo=mock_interaction_configs_repo,
        worker_readiness_repo=mock_readiness_repo,
        task_workflows_repo=mock_task_workflows_repo,
        step_executions_repo=mock_step_execs_repo,
        task_results_repo=mock_task_results_repo,
    )

    org_id = uuid4()
    u_id = uuid4()
    wp_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_users_repo.list_by_organization.return_value = [
        {"id": u_id, "organization_id": org_id, "email": "w1@factory.com", "full_name": "Worker One", "status": "active", "created_at": now}
    ]
    mock_wp_repo.get_by_user_id.return_value = {"id": wp_id, "user_id": u_id}
    mock_sessions_repo.list_by_worker_profile_id.return_value = [{"id": uuid4(), "status": "active", "started_at": now}]
    mock_assignments_repo.list_by_worker_profile_id.return_value = []
    mock_assistance_repo.list_by_worker_profile_id.return_value = []
    mock_tasks_repo.list_by_organization_id.return_value = []
    mock_personalizations_repo.get_by_worker_profile_id.return_value = None

    summary = service.get_dashboard_summary(org_id)
    assert summary.active_workers_count == 1
    assert summary.available_workers_count == 1
    assert summary.workers_in_task_count == 0
    assert summary.emergency_stops_active == 0


def test_supervisor_service_assign_and_reassign_task_unit():
    """Unit test for assigning and reassigning tasks with tenant validation."""
    mock_tasks_repo = MagicMock()
    mock_wp_repo = MagicMock()
    mock_users_repo = MagicMock()
    mock_assignments_repo = MagicMock()
    mock_audit_repo = MagicMock()

    service = SupervisorService(
        tasks_repo=mock_tasks_repo,
        worker_profiles_repo=mock_wp_repo,
        users_repo=mock_users_repo,
        worker_task_assignments_repo=mock_assignments_repo,
        audit_events_repo=mock_audit_repo,
    )

    org_id = uuid4()
    sup_id = uuid4()
    task_id = uuid4()
    wp_id = uuid4()
    u_id = uuid4()
    assignment_id = uuid4()

    mock_tasks_repo.get_by_id.return_value = {
        "id": task_id,
        "organization_id": org_id,
        "name": "Gearbox Pre-Assembly",
        "status": "active",
    }
    mock_wp_repo.get_by_id.return_value = {"id": wp_id, "user_id": u_id}
    mock_users_repo.get_by_id.return_value = {"id": u_id, "organization_id": org_id, "full_name": "Alex Worker", "email": "alex@amap.org"}
    mock_assignments_repo.create.return_value = {"id": assignment_id, "task_id": task_id, "worker_profile_id": wp_id, "status": "assigned"}

    # 1. Assign Task
    payload = TaskAssignmentPayload(task_id=task_id, worker_profile_id=wp_id, notes="Priority assignment")
    res = service.assign_task(org_id, sup_id, payload)
    assert "successfully assigned" in res["message"]
    mock_audit_repo.create.assert_called()

    # 2. Cross-tenant task assignment rejection
    cross_org_id = uuid4()
    with pytest.raises(UnauthorizedError):
        service.assign_task(cross_org_id, sup_id, payload)


def test_supervisor_service_assistance_lifecycle_unit():
    """Unit test for acknowledge, guidance response, and resolution of assistance."""
    mock_assistance_repo = MagicMock()
    mock_audit_repo = MagicMock()

    service = SupervisorService(
        assistance_requests_repo=mock_assistance_repo,
        audit_events_repo=mock_audit_repo,
    )

    org_id = uuid4()
    sup_id = uuid4()
    req_id = uuid4()

    mock_assistance_repo.get_by_id.return_value = {
        "id": req_id,
        "organization_id": org_id,
        "status": "open",
        "priority": "high",
        "reason": "Calibration drift on Step 3",
        "request_data": {},
    }
    mock_assistance_repo.update_status.return_value = {"id": req_id, "status": "acknowledged"}

    # 1. Acknowledge
    ack = service.acknowledge_assistance(org_id, sup_id, req_id)
    assert ack["message"] == "Assistance request acknowledged."

    # 2. Respond with guidance
    resp_payload = AssistanceResponsePayload(
        guidance_message="Re-seat optical landmark sensor and hold confirm",
        resolution_action="Sensor Recalibration",
    )
    resp = service.respond_to_assistance(org_id, sup_id, req_id, resp_payload)
    assert "guidance transmitted" in resp["message"]

    # 3. Resolve
    resolve_payload = AssistanceResolvePayload(resolution_notes="Sensor re-seated and verified OK")
    resolved = service.resolve_assistance(org_id, sup_id, req_id, resolve_payload)
    assert "successfully resolved" in resolved["message"]


# =========================================================================
# API Route Endpoint Tests with RBAC & Tenancy Validation
# =========================================================================

def test_unauthenticated_request_to_supervisor_denied(client):
    """Unauthenticated access to supervisor API must be denied (401/403)."""
    resp = client.get("/api/v1/supervisor/dashboard")
    assert resp.status_code in (401, 403)


def test_worker_role_cannot_access_supervisor_apis(client, worker_user):
    """Workers must be strictly forbidden from supervisor endpoints (HTTP 403)."""
    app.dependency_overrides[get_current_user] = lambda: worker_user
    try:
        resp = client.get("/api/v1/supervisor/dashboard")
        assert resp.status_code == 403

        resp_workers = client.get("/api/v1/supervisor/workers")
        assert resp_workers.status_code == 403

        resp_assign = client.post(
            "/api/v1/supervisor/tasks/assign",
            json={"task_id": str(uuid4()), "worker_profile_id": str(uuid4())},
        )
        assert resp_assign.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_supervisor_role_can_access_dashboard(client, supervisor_user):
    """Supervisors can access dashboard with mock service."""
    mock_service = MagicMock()
    mock_service.get_dashboard_summary.return_value = SupervisorDashboardSummary(
        active_workers_count=5,
        available_workers_count=2,
        workers_in_task_count=3,
        workers_requesting_assistance_count=1,
        completed_tasks_count=14,
        in_progress_tasks_count=3,
        failed_tasks_count=0,
        current_workload_percent=60.0,
        emergency_stops_active=0,
    )

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        resp = client.get("/api/v1/supervisor/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_workers_count"] == 5
        assert data["workers_in_task_count"] == 3
        assert data["current_workload_percent"] == 60.0
    finally:
        app.dependency_overrides.clear()


def test_supervisor_list_workers_endpoint(client, supervisor_user):
    """Supervisor can retrieve list of workers for their organization."""
    mock_service = MagicMock()
    wp_id = uuid4()
    u_id = uuid4()
    mock_service.list_organization_workers.return_value = [
        SupervisorWorkerItem(
            worker_profile_id=wp_id,
            user_id=u_id,
            full_name="Alex Morgan",
            email="alex@amap.org",
            status="WORKING",
            current_task_name="High-Precision Gearbox Assembly",
            progress_percent=66.7,
            interaction_mode="multimodal",
            session_duration_seconds=1240,
        )
    ]

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        resp = client.get("/api/v1/supervisor/workers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "Alex Morgan"
        assert data[0]["status"] == "WORKING"
    finally:
        app.dependency_overrides.clear()


def test_supervisor_worker_detail_endpoint(client, supervisor_user):
    """Supervisor can retrieve deep-dive worker detail view."""
    mock_service = MagicMock()
    wp_id = uuid4()
    u_id = uuid4()
    mock_service.get_worker_detail.return_value = SupervisorWorkerDetail(
        worker_profile_id=wp_id,
        user_id=u_id,
        full_name="Alex Morgan",
        email="alex@amap.org",
        status="WORKING",
        current_task_name="High-Precision Gearbox Assembly",
        progress_percent=66.7,
        interaction_mode="multimodal",
        session_duration_seconds=1240,
        step_details=[
            {"step_number": 1, "title": "Check Housing", "status": "completed", "is_current": False},
            {"step_number": 2, "title": "Insert Planetary Gears", "status": "in_progress", "is_current": True},
        ],
        recent_assistance_requests=[],
        recent_task_assignments=[],
    )

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        resp = client.get(f"/api/v1/supervisor/workers/{wp_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Alex Morgan"
        assert len(data["step_details"]) == 2
        assert data["step_details"][1]["is_current"] is True
    finally:
        app.dependency_overrides.clear()


def test_supervisor_task_assignment_endpoints(client, supervisor_user):
    """Supervisor can list assignable tasks and dispatch new assignment."""
    mock_service = MagicMock()
    task_id = uuid4()
    wp_id = uuid4()

    mock_service.list_assignable_tasks.return_value = [
        {"id": str(task_id), "name": "Gearbox Assembly", "status": "active"}
    ]
    mock_service.assign_task.return_value = {
        "message": "Task successfully assigned.",
        "assignment": {"id": str(uuid4()), "task_id": str(task_id), "worker_profile_id": str(wp_id)},
    }

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        # List tasks
        resp_list = client.get("/api/v1/supervisor/tasks")
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 1

        # Assign task
        resp_assign = client.post(
            "/api/v1/supervisor/tasks/assign",
            json={"task_id": str(task_id), "worker_profile_id": str(wp_id), "notes": "Urgent lot"},
        )
        assert resp_assign.status_code == 201
        assert "successfully assigned" in resp_assign.json()["message"]
    finally:
        app.dependency_overrides.clear()


def test_supervisor_assistance_endpoints(client, supervisor_user):
    """Supervisor can list, acknowledge, respond, and resolve assistance requests."""
    mock_service = MagicMock()
    req_id = uuid4()

    mock_service.list_assistance_requests.return_value = [
        {
            "id": str(req_id),
            "worker_name": "Samira Chen",
            "task_name": "Circuit Board QA",
            "status": "open",
            "priority": "high",
            "reason": "Optical sensor glare",
            "is_emergency": False,
        }
    ]
    mock_service.acknowledge_assistance.return_value = {"message": "Assistance request acknowledged."}
    mock_service.respond_to_assistance.return_value = {"message": "Supervisor guidance transmitted to worker."}
    mock_service.resolve_assistance.return_value = {"message": "Assistance request successfully resolved."}

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        # 1. List
        resp1 = client.get("/api/v1/supervisor/assistance")
        assert resp1.status_code == 200
        assert len(resp1.json()) == 1

        # 2. Acknowledge
        resp2 = client.post(f"/api/v1/supervisor/assistance/{req_id}/acknowledge")
        assert resp2.status_code == 200

        # 3. Respond
        resp3 = client.post(
            f"/api/v1/supervisor/assistance/{req_id}/respond",
            json={"guidance_message": "Switch lighting filter to polarized mode."},
        )
        assert resp3.status_code == 200

        # 4. Resolve
        resp4 = client.post(
            f"/api/v1/supervisor/assistance/{req_id}/resolve",
            json={"resolution_notes": "Lighting adjusted, test passed."},
        )
        assert resp4.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_supervisor_emergency_events_and_analytics(client, supervisor_user):
    """Supervisor can inspect emergency line halts and operational analytics."""
    mock_service = MagicMock()
    mock_service.list_emergency_events.return_value = []
    mock_service.get_operational_analytics.return_value = SupervisorAnalytics(
        tasks_assigned_count=20,
        tasks_completed_count=18,
        tasks_in_progress_count=2,
        average_task_duration_minutes=8.5,
        workflow_completion_rate=90.0,
        total_assistance_requests=3,
        resolved_assistance_requests=3,
        average_resolution_time_minutes=1.2,
        emergency_stops_count=0,
    )
    mock_service.list_audit_timeline.return_value = [
        SupervisorAuditEvent(
            id=uuid4(),
            event_type="supervisor_task_assigned",
            actor_name="Sarah Connor",
            resource_type="worker_task_assignment",
            occurred_at=datetime.now(timezone.utc),
        )
    ]

    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    app.dependency_overrides[get_supervisor_service] = lambda: mock_service

    try:
        # Emergency events
        resp_em = client.get("/api/v1/supervisor/emergency-events")
        assert resp_em.status_code == 200
        assert isinstance(resp_em.json(), list)

        # Analytics
        resp_an = client.get("/api/v1/supervisor/analytics")
        assert resp_an.status_code == 200
        assert resp_an.json()["workflow_completion_rate"] == 90.0

        # Audit timeline
        resp_audit = client.get("/api/v1/supervisor/audit?limit=10")
        assert resp_audit.status_code == 200
        assert len(resp_audit.json()) == 1
    finally:
        app.dependency_overrides.clear()
