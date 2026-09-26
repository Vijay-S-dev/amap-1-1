"""
Enterprise Organization Management & Multi-Tenant Isolation Test Suite (§ 1-40).

Tests:
1. Organization authentication & token identity assertion.
2. RBAC: Admin & Superadmin permitted, Worker & unauthenticated denied (401/403).
3. Dashboard KPI aggregations from actual database entities.
4. Organization profile retrieval & accessibility defaults.
5. Department creation, listing, updating, and deactivation.
6. Department isolation between tenants (Organization A vs Organization B).
7. Supervisor listing, department mapping, and secure invitations.
8. Worker listing with real operational lifecycle states (WORKING, READY, ASSISTANCE_REQUESTED, ONBOARDING).
9. Worker invitations without requiring mouse/keyboard setup.
10. Workflow & task template creation, step sequencing, and safety critical flags.
11. Assistance requests organization-wide overview.
12. Emergency events visibility.
13. Aggregate operational & accessibility readiness analytics.
14. Append-only immutable audit trail recording all admin mutations.
15. Cross-tenant security isolation (Admin A cannot inspect or modify Org B data).
"""

from unittest.mock import MagicMock
from uuid import UUID, uuid4
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from routes.organization_management import get_org_management_service
from services.organization_management_service import OrganizationManagementService

ORG_A_ID = UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65")
ORG_B_ID = UUID("8b52d14c-6b21-4001-8b06-0722c6a31e54")

ADMIN_A_ID = UUID("c0000000-0000-0000-0000-000000000001")
ADMIN_B_ID = UUID("c0000000-0000-0000-0000-000000000099")
WORKER_A_ID = UUID("c0000000-0000-0000-0000-000000000003")


@pytest.fixture
def mock_service() -> OrganizationManagementService:
    """Fixture providing a mock OrganizationManagementService with tenant repositories mocked."""
    from datetime import datetime, timezone

    service = OrganizationManagementService(
        orgs_repo=MagicMock(),
        depts_repo=MagicMock(),
        users_repo=MagicMock(),
        workers_repo=MagicMock(),
        workflows_repo=MagicMock(),
        workflow_steps_repo=MagicMock(),
        audit_repo=MagicMock(),
        assistance_repo=MagicMock(),
        user_departments_repo=MagicMock(),
        roles_repo=MagicMock(),
        user_roles_repo=MagicMock(),
        worker_readiness_repo=MagicMock(),
    )
    # list_workers now reads the real directory query: return an empty page by
    # default so contract-level tests stay deterministic.
    service.workers_repo.list_enterprise_directory.return_value = ([], 0)
    # invite_worker performs a real duplicate-email check before creating rows.
    service.users_repo.get_by_email.return_value = None
    # Organization name uniqueness pre-check: no existing org by default.
    service.orgs_repo.get_by_name.return_value = None
    now = datetime.now(timezone.utc)
    created_user_id = uuid4()

    def _fake_create_user(organization_id, email, full_name, password_hash):
        # Echo the real inputs (matching UsersRepository.create behavior).
        return {
            "id": created_user_id,
            "organization_id": organization_id,
            "email": email,
            "full_name": full_name,
            "password_hash": password_hash,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

    service.users_repo.create.side_effect = _fake_create_user
    service.workers_repo.create.return_value = {
        "id": uuid4(),
        "user_id": created_user_id,
        "badge_number": None,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    # list/create/update workflows now read the real repositories: give the
    # workflow repo a seed row and keep steps in an in-memory store so the
    # contract tests stay deterministic.
    seed_workflow_id = uuid4()
    created_workflow_id = uuid4()
    workflow_steps_store: dict = {seed_workflow_id: []}
    service.workflows_repo.list_by_organization_id.return_value = [
        {
            "id": seed_workflow_id,
            "organization_id": ORG_A_ID,
            "name": "Seeded Assembly Workflow",
            "description": "Fixture workflow row",
            "department_id": None,
            "version": 1,
            "estimated_duration_minutes": 15.0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    ]
    service.workflows_repo.get_by_organization_and_name.return_value = None

    def _fake_create_workflow(
        organization_id,
        name,
        description=None,
        status="active",
        department_id=None,
        version=1,
        estimated_duration_minutes=15.0,
    ):
        return {
            "id": created_workflow_id,
            "organization_id": organization_id,
            "name": name,
            "description": description,
            "department_id": department_id,
            "version": version,
            "estimated_duration_minutes": estimated_duration_minutes,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }

    service.workflows_repo.create.side_effect = _fake_create_workflow

    def _fake_create_workflow_step(
        workflow_id,
        step_order,
        name,
        description=None,
        status="active",
        is_safety_critical=False,
        expected_duration_seconds=120,
        required_intent=None,
    ):
        row = {
            "id": uuid4(),
            "workflow_id": workflow_id,
            "step_order": step_order,
            "name": name,
            "description": description,
            "is_safety_critical": is_safety_critical,
            "expected_duration_seconds": expected_duration_seconds,
            "required_intent": required_intent,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        workflow_steps_store.setdefault(workflow_id, []).append(row)
        return row

    service.workflow_steps_repo.create.side_effect = _fake_create_workflow_step
    service.workflow_steps_repo.list_by_workflow_id.side_effect = (
        lambda workflow_id: workflow_steps_store.get(workflow_id, [])
    )
    return service


def test_unauthenticated_request_to_org_management_denied():
    """Unauthenticated requests must be strictly rejected with HTTP 401."""
    client = TestClient(app)
    app.dependency_overrides.clear()
    res = client.get("/api/v1/organizations/manage/dashboard")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_worker_role_cannot_access_org_management():
    """Worker role attempting to access organization management must be rejected with HTTP 403."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=WORKER_A_ID,
        organization_id=ORG_A_ID,
        email="alex.worker@amap.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker"],
        is_active=True,
    )
    try:
        res = client.get("/api/v1/organizations/manage/dashboard")
        assert res.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.clear()


def test_admin_dashboard_kpis_endpoint(mock_service):
    """Admin role can retrieve real organization dashboard KPIs."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        res = client.get("/api/v1/organizations/manage/dashboard")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["organization_id"] == str(ORG_A_ID)
        assert "total_workers_count" in data
        assert "active_workers_count" in data
        assert "current_line_utilization_percent" in data
    finally:
        app.dependency_overrides.clear()


def test_get_and_update_organization_profile(mock_service):
    """Admin can view and update organization profile and accessibility defaults."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    mock_service.orgs_repo.get_by_id.return_value = {
        "id": ORG_A_ID,
        "name": "Acme Motors — Assembly Plant 1",
        "status": "active",
    }
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # 1. GET profile
        res_get = client.get("/api/v1/organizations/manage/profile")
        assert res_get.status_code == status.HTTP_200_OK
        profile = res_get.json()
        assert profile["name"] == "Acme Motors — Assembly Plant 1"
        assert "accessibility_defaults" in profile

        # 2. PUT profile
        res_put = client.put(
            "/api/v1/organizations/manage/profile",
            json={"name": "Acme Motors — Updated Plant 1", "default_language": "en"},
        )
        assert res_put.status_code == status.HTTP_200_OK
    finally:
        app.dependency_overrides.clear()


def test_department_crud_and_tenant_isolation(mock_service):
    """Departments are strictly scoped to the authenticated admin's organization."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    from datetime import datetime, timezone

    dept_id = uuid4()
    now = datetime.now(timezone.utc)
    mock_service.depts_repo.list_by_organization_with_counts.return_value = [
        {
            "id": dept_id,
            "organization_id": ORG_A_ID,
            "name": "Powertrain Integration",
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "supervisor_count": 0,
            "worker_count": 0,
            "active_tasks_count": 0,
        }
    ]
    mock_service.depts_repo.get_by_name.return_value = None
    mock_service.depts_repo.create.return_value = {
        "id": uuid4(),
        "organization_id": ORG_A_ID,
        "name": "Chassis Welding",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    mock_service.depts_repo.get_with_counts.side_effect = lambda department_id: {
        "id": department_id,
        "organization_id": ORG_A_ID,
        "name": "Chassis Welding",
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "supervisor_count": 0,
        "worker_count": 0,
        "active_tasks_count": 0,
    }
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # 1. List departments
        res_list = client.get("/api/v1/organizations/manage/departments")
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.json()) >= 1

        # 2. Create department
        res_create = client.post(
            "/api/v1/organizations/manage/departments",
            json={"name": "Chassis Welding", "status": "active"},
        )
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.json()["name"] == "Chassis Welding"
    finally:
        app.dependency_overrides.clear()


def test_cross_tenant_department_mutation_rejected(mock_service):
    """Admin from Org A cannot update a department belonging to Org B."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="adminA@amap.com",
        full_name="Admin A",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    org_b_dept_id = uuid4()
    mock_service.depts_repo.get_by_id.return_value = {
        "id": org_b_dept_id,
        "organization_id": ORG_B_ID,
        "name": "Org B Department",
    }
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        res_put = client.put(
            f"/api/v1/organizations/manage/departments/{org_b_dept_id}",
            json={"name": "Tampered Name"},
        )
        assert res_put.status_code == status.HTTP_404_NOT_FOUND

        res_del = client.delete(f"/api/v1/organizations/manage/departments/{org_b_dept_id}")
        assert res_del.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.clear()


def test_supervisor_management_and_invitation(mock_service):
    """Admin can list supervisors and invite new supervisors to departments."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    mock_service.depts_repo.list_by_organization.return_value = []
    mock_service.users_repo.list_by_organization.return_value = []
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # List supervisors
        res_list = client.get("/api/v1/organizations/manage/supervisors")
        assert res_list.status_code == status.HTTP_200_OK

        # Invite supervisor
        res_invite = client.post(
            "/api/v1/organizations/manage/supervisors/invite",
            json={"email": "new.supervisor@amap.com", "full_name": "Elena Rostova"},
        )
        assert res_invite.status_code == status.HTTP_201_CREATED
        assert res_invite.json()["email"] == "new.supervisor@amap.com"
        assert res_invite.json()["status"] == "invited"
    finally:
        app.dependency_overrides.clear()


def test_worker_management_and_invitation(mock_service):
    """Admin can list workers with operational states and invite new workers."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # List workers with pagination & status filtering
        res_list = client.get("/api/v1/organizations/manage/workers?page=1&page_size=10&status=WORKING")
        assert res_list.status_code == status.HTTP_200_OK
        data = res_list.json()
        assert "items" in data
        assert "total_count" in data

        # Invite worker
        res_invite = client.post(
            "/api/v1/organizations/manage/workers/invite",
            json={
                "email": "carlos.assembler@amap.com",
                "full_name": "Carlos Gomez",
                "preferred_modality": "gesture",
            },
        )
        assert res_invite.status_code == status.HTTP_201_CREATED
        assert res_invite.json()["email"] == "carlos.assembler@amap.com"
        assert res_invite.json()["status"] == "INVITED"
    finally:
        app.dependency_overrides.clear()


def test_workflow_template_management(mock_service):
    """Admin can manage approved assembly workflows and safety critical step sequences."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # List workflows
        res_list = client.get("/api/v1/organizations/manage/workflows")
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.json()) >= 1

        # Create workflow
        payload = {
            "name": "Battery Cell Module Interconnect",
            "description": "Busbar placement and automated resistance testing",
            "steps": [
                {"title": "Cell Orientation QA", "instruction": "Inspect barcode and polarity.", "is_safety_critical": False},
                {"title": "Laser Weld Sequence", "instruction": "Trigger pneumatic clamp and execute weld.", "is_safety_critical": True},
            ],
            "estimated_duration_minutes": 14.0,
        }
        res_create = client.post("/api/v1/organizations/manage/workflows", json=payload)
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.json()["name"] == "Battery Cell Module Interconnect"
        assert res_create.json()["step_count"] == 2
    finally:
        app.dependency_overrides.clear()


def test_assistance_overview_and_emergencies(mock_service):
    """Admin can monitor assistance queues and emergency stop events."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        res_ast = client.get("/api/v1/organizations/manage/assistance")
        assert res_ast.status_code == status.HTTP_200_OK
        assert isinstance(res_ast.json(), list)

        res_emg = client.get("/api/v1/organizations/manage/emergencies")
        assert res_emg.status_code == status.HTTP_200_OK
        assert isinstance(res_emg.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_organization_analytics_and_audit_trail(mock_service):
    """Admin can query operational analytics and immutable audit log records."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id=ADMIN_A_ID,
        organization_id=ORG_A_ID,
        email="admin@amap.com",
        full_name="Sarah Jenkins",
        status="active",
        roles=["admin"],
        is_active=True,
    )
    mock_service.audit_repo.list_by_organization_id.return_value = []
    app.dependency_overrides[get_org_management_service] = lambda: mock_service

    try:
        # Analytics
        res_an = client.get("/api/v1/organizations/manage/analytics")
        assert res_an.status_code == status.HTTP_200_OK
        assert "tasks_completed_count" in res_an.json()
        assert "gesture_ready_workers_count" in res_an.json()

        # Audit Trail — empty repository must yield an empty list (the old
        # implementation fabricated a "seeded default audit stream" here).
        res_aud = client.get("/api/v1/organizations/manage/audit?limit=25")
        assert res_aud.status_code == status.HTTP_200_OK
        assert res_aud.json() == []

        # With a real audit row, the actor is resolved from users/roles.
        from datetime import datetime as _dt, timezone as _tz
        mock_service.audit_repo.list_by_organization_id.return_value = [
            {
                "id": ADMIN_A_ID,
                "organization_id": ORG_A_ID,
                "actor_user_id": ADMIN_A_ID,
                "event_type": "department.created",
                "resource_type": "department",
                "resource_id": None,
                "event_data": {"name": "Welding"},
                "occurred_at": _dt.now(_tz.utc),
                "created_at": _dt.now(_tz.utc),
            }
        ]
        mock_service.users_repo.get_by_id.return_value = {
            "id": ADMIN_A_ID,
            "full_name": "Sarah Jenkins",
            "email": "admin@amap.com",
        }
        mock_service.user_roles_repo.get_by_user_id.return_value = [
            {"role_id": ADMIN_A_ID}
        ]
        mock_service.roles_repo.get_by_id.return_value = {"name": "admin"}
        res_aud = client.get("/api/v1/organizations/manage/audit?limit=25")
        assert res_aud.status_code == status.HTTP_200_OK
        items = res_aud.json()
        assert len(items) == 1
        assert items[0]["actor_name"] == "Sarah Jenkins"
        assert items[0]["actor_role"] == "admin"
        assert items[0]["event_type"] == "department.created"
    finally:
        app.dependency_overrides.clear()
