"""
Tests for AMAP Admin and System Configuration Functionality (Phase 13).
Covers interaction configuration CRUD, tenant organization settings, user/role management,
audit event queries, and strict RBAC authorization gating.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.interaction import InteractionConfigurationCreate, InteractionConfigurationUpdate
from models.organization import OrganizationUpdate
from routes.admin import get_admin_service
from services.admin_service import AdminService
from services.base import NotFoundError


# =====================================================================
# Unit Tests for AdminService
# =====================================================================

def test_admin_configs_crud_and_audit():
    mock_configs_repo = MagicMock()
    mock_audit_repo = MagicMock()

    service = AdminService(
        configs_repo=mock_configs_repo,
        audit_repo=mock_audit_repo,
    )

    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    config_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Create config
    mock_configs_repo.create.return_value = {
        "id": config_id,
        "organization_id": org_id,
        "name": "Station A Preset",
        "description": "High noise preset",
        "config_data": {"dwell_time_ms": 600},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    create_payload = InteractionConfigurationCreate(
        organization_id=org_id,
        name="Station A Preset",
        description="High noise preset",
        config_data={"dwell_time_ms": 600},
    )

    created = service.create_config(organization_id=org_id, payload=create_payload, actor_id=actor_id)
    assert created.name == "Station A Preset"
    assert created.config_data == {"dwell_time_ms": 600}
    mock_audit_repo.create.assert_called_once()

    # 2. Get config
    mock_configs_repo.get_by_id.return_value = {
        "id": config_id,
        "organization_id": org_id,
        "name": "Station A Preset",
        "description": "High noise preset",
        "config_data": {"dwell_time_ms": 600},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    fetched = service.get_config(config_id=config_id, organization_id=org_id)
    assert fetched.id == config_id

    # 3. Update config
    mock_configs_repo.update.return_value = {
        "id": config_id,
        "organization_id": org_id,
        "name": "Station A Preset V2",
        "description": "High noise preset updated",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    update_payload = InteractionConfigurationUpdate(
        name="Station A Preset V2",
        description="High noise preset updated",
    )
    updated = service.update_config(
        config_id=config_id,
        organization_id=org_id,
        payload=update_payload,
        actor_id=actor_id,
    )
    assert updated.name == "Station A Preset V2"

    # 4. Delete config
    mock_configs_repo.delete_by_id.return_value = True
    deleted = service.delete_config(config_id=config_id, organization_id=org_id, actor_id=actor_id)
    assert deleted is True


def test_admin_user_and_role_management():
    mock_users_repo = MagicMock()
    mock_roles_repo = MagicMock()
    mock_user_roles_repo = MagicMock()
    mock_audit_repo = MagicMock()

    service = AdminService(
        users_repo=mock_users_repo,
        roles_repo=mock_roles_repo,
        user_roles_repo=mock_user_roles_repo,
        audit_repo=mock_audit_repo,
    )

    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Update user status
    mock_users_repo.get_by_id.return_value = {
        "id": target_user_id,
        "organization_id": org_id,
        "email": "target@amap.org",
        "full_name": "Target User",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    mock_users_repo.update_status.return_value = {
        "id": target_user_id,
        "organization_id": org_id,
        "email": "target@amap.org",
        "full_name": "Target User",
        "status": "suspended",
        "created_at": now,
        "updated_at": now,
    }

    updated_user = service.update_user_status(
        user_id=target_user_id,
        organization_id=org_id,
        new_status="suspended",
        actor_id=actor_id,
        reason="Security audit review",
    )
    assert updated_user.status == "suspended"

    # 2. Assign role
    mock_roles_repo.get_by_name.return_value = {
        "id": role_id,
        "name": "supervisor",
        "description": "Supervisor Role",
        "created_at": now,
        "updated_at": now,
    }
    mock_user_roles_repo.get.return_value = None
    mock_user_roles_repo.create.return_value = {
        "user_id": target_user_id,
        "role_id": role_id,
        "created_at": now,
    }

    assignment = service.assign_role(
        user_id=target_user_id,
        role_name="supervisor",
        organization_id=org_id,
        actor_id=actor_id,
    )
    assert assignment["role_id"] == role_id

    # 3. Revoke role
    mock_user_roles_repo.delete.return_value = True
    revoked = service.revoke_role(
        user_id=target_user_id,
        role_name="supervisor",
        organization_id=org_id,
        actor_id=actor_id,
    )
    assert revoked is True


def test_admin_audit_log_querying():
    mock_audit_repo = MagicMock()
    service = AdminService(audit_repo=mock_audit_repo)

    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_audit_repo.list_by_organization_id.return_value = [
        {
            "id": uuid.uuid4(),
            "organization_id": org_id,
            "actor_user_id": actor_id,
            "event_type": "user.status_updated",
            "resource_type": "user",
            "resource_id": uuid.uuid4(),
            "event_data": {"new_status": "suspended"},
            "occurred_at": now,
            "created_at": now,
        },
        {
            "id": uuid.uuid4(),
            "organization_id": org_id,
            "actor_user_id": actor_id,
            "event_type": "interaction_config.created",
            "resource_type": "interaction_configuration",
            "resource_id": uuid.uuid4(),
            "event_data": {},
            "occurred_at": now,
            "created_at": now,
        },
    ]

    # Query all
    logs = service.query_audit_logs(organization_id=org_id)
    assert len(logs) == 2

    # Query filtered by event_type
    filtered = service.query_audit_logs(organization_id=org_id, event_type="user.status_updated")
    assert len(filtered) == 1
    assert filtered[0].event_type == "user.status_updated"


# =====================================================================
# API Route Endpoint Tests with RBAC Validation
# =====================================================================

def test_admin_endpoints_admin_success():
    client = TestClient(app)
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_admin = AuthenticatedUserContext(
        user_id=admin_id,
        organization_id=org_id,
        email="admin@amap.org",
        full_name="Admin",
        status="active",
        roles=["admin"],
        permissions=["admin:manage_configs", "admin:manage_users", "admin:view_audit"],
    )

    mock_service = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_admin_service] = lambda: mock_service

    try:
        now = datetime.now(timezone.utc)
        # 1. GET /api/v1/admin/configs
        mock_service.list_configs.return_value = []
        resp1 = client.get("/api/v1/admin/configs")
        assert resp1.status_code == 200

        # 2. GET /api/v1/admin/organization
        mock_service.get_organization.return_value = {
            "id": org_id,
            "name": "Acme Industries",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        resp2 = client.get("/api/v1/admin/organization")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Acme Industries"

        # 3. GET /api/v1/admin/audit-logs
        mock_service.query_audit_logs.return_value = []
        resp3 = client.get("/api/v1/admin/audit-logs?limit=10")
        assert resp3.status_code == 200

    finally:
        app.dependency_overrides.clear()


def test_admin_endpoints_non_admin_forbidden():
    client = TestClient(app)
    org_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    # Worker role only
    mock_worker = AuthenticatedUserContext(
        user_id=worker_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=["session:start", "task:read"],
        worker_profile_id=uuid.uuid4(),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_worker

    try:
        # Non-admin attempting to access admin endpoints must receive 403 Forbidden
        resp1 = client.get("/api/v1/admin/configs")
        assert resp1.status_code == 403

        resp2 = client.get("/api/v1/admin/organization")
        assert resp2.status_code == 403

        resp3 = client.get("/api/v1/admin/audit-logs")
        assert resp3.status_code == 403

    finally:
        app.dependency_overrides.clear()
