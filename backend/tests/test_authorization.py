"""
Tests for AMAP Authorization, RBAC, and Organization Isolation (Phase 6).
"""

import uuid
import pytest
from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.testclient import TestClient

from app.dependencies import (
    get_current_user,
    require_permissions,
    require_roles,
    validate_organization_access,
    validate_worker_access,
)
from models.auth import AuthenticatedUserContext
from services.authorization_service import AuthorizationService
from services.base import UnauthorizedError


# =====================================================================
# AuthorizationService Unit Tests
# =====================================================================

def test_authz_service_permissions():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    worker_user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker User",
        status="active",
        roles=["worker"],
        permissions=["tasks:read", "tasks:write"],
    )

    admin_user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="admin@amap.org",
        full_name="Admin User",
        status="active",
        roles=["admin"],
        permissions=[],
    )

    # Worker checks
    assert AuthorizationService.has_permission(worker_user, "tasks:read") is True
    assert AuthorizationService.has_permission(worker_user, "users:delete") is False
    assert (
        AuthorizationService.has_all_permissions(
            worker_user, ["tasks:read", "tasks:write"]
        )
        is True
    )
    assert (
        AuthorizationService.has_all_permissions(
            worker_user, ["tasks:read", "users:delete"]
        )
        is False
    )

    # Admin checks (admin override)
    assert AuthorizationService.has_permission(admin_user, "users:delete") is True
    assert (
        AuthorizationService.has_all_permissions(
            admin_user, ["users:delete", "org:manage"]
        )
        is True
    )


def test_authz_service_roles():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="sup@amap.org",
        full_name="Supervisor User",
        status="active",
        roles=["supervisor"],
        permissions=[],
    )

    assert AuthorizationService.has_any_role(user, ["supervisor", "manager"]) is True
    assert AuthorizationService.has_any_role(user, ["admin", "superadmin"]) is False


def test_authz_service_organization_isolation():
    org_1 = uuid.uuid4()
    org_2 = uuid.uuid4()
    user_id = uuid.uuid4()

    user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_1,
        email="user@org1.com",
        full_name="Org 1 User",
        status="active",
        roles=["worker"],
        permissions=[],
    )

    # Same org passes
    AuthorizationService.assert_same_organization(user, org_1)

    # Different org raises UnauthorizedError
    with pytest.raises(UnauthorizedError, match="Cross-organization access denied"):
        AuthorizationService.assert_same_organization(user, org_2)


def test_authz_service_worker_access():
    org_id = uuid.uuid4()
    worker_1_id = uuid.uuid4()
    worker_2_id = uuid.uuid4()

    worker_1 = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=org_id,
        email="w1@amap.org",
        full_name="Worker 1",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=worker_1_id,
    )

    supervisor = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=org_id,
        email="sup@amap.org",
        full_name="Supervisor",
        status="active",
        roles=["supervisor"],
        permissions=[],
        worker_profile_id=None,
    )

    # Worker 1 can access self
    assert AuthorizationService.can_access_worker(worker_1, worker_1_id) is True
    # Worker 1 cannot access Worker 2
    assert AuthorizationService.can_access_worker(worker_1, worker_2_id) is False
    # Supervisor can access Worker 2
    assert AuthorizationService.can_access_worker(supervisor, worker_2_id) is True


# =====================================================================
# FastAPI Dependency Integration Tests
# =====================================================================

dummy_app = FastAPI()
dummy_router = APIRouter()


@dummy_router.get(
    "/protected/permissions",
    dependencies=[Depends(require_permissions("audit:read"))],
)
def protected_perm_route():
    return {"message": "permission granted"}


@dummy_router.get(
    "/protected/roles",
    dependencies=[Depends(require_roles("admin", "manager"))],
)
def protected_role_route():
    return {"message": "role granted"}


@dummy_router.get("/protected/org/{org_id}")
def protected_org_route(
    org_id: uuid.UUID,
    user: AuthenticatedUserContext = Depends(get_current_user),
):
    validate_organization_access(org_id, user)
    return {"message": "org access granted"}


@dummy_router.get("/protected/worker/{worker_id}")
def protected_worker_route(
    worker_id: uuid.UUID,
    user: AuthenticatedUserContext = Depends(get_current_user),
):
    validate_worker_access(worker_id, user)
    return {"message": "worker access granted"}


dummy_app.include_router(dummy_router)


def test_dependency_permission_gate():
    client = TestClient(dummy_app)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # User WITHOUT permission
    user_no_perm = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="user@amap.org",
        full_name="Test User",
        status="active",
        roles=["worker"],
        permissions=["tasks:read"],
    )

    dummy_app.dependency_overrides[get_current_user] = lambda: user_no_perm
    try:
        resp = client.get("/protected/permissions")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # User WITH permission
        user_with_perm = AuthenticatedUserContext(
            user_id=user_id,
            organization_id=org_id,
            email="auditor@amap.org",
            full_name="Auditor",
            status="active",
            roles=["auditor"],
            permissions=["audit:read"],
        )
        dummy_app.dependency_overrides[get_current_user] = lambda: user_with_perm
        resp = client.get("/protected/permissions")
        assert resp.status_code == status.HTTP_200_OK
    finally:
        dummy_app.dependency_overrides.clear()


def test_dependency_role_gate():
    client = TestClient(dummy_app)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # User WITHOUT role
    worker_user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
    )

    dummy_app.dependency_overrides[get_current_user] = lambda: worker_user
    try:
        resp = client.get("/protected/roles")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # User WITH manager role
        manager_user = AuthenticatedUserContext(
            user_id=user_id,
            organization_id=org_id,
            email="mgr@amap.org",
            full_name="Manager",
            status="active",
            roles=["manager"],
            permissions=[],
        )
        dummy_app.dependency_overrides[get_current_user] = lambda: manager_user
        resp = client.get("/protected/roles")
        assert resp.status_code == status.HTTP_200_OK
    finally:
        dummy_app.dependency_overrides.clear()


def test_dependency_org_isolation_and_worker_access():
    client = TestClient(dummy_app)
    org_1 = uuid.uuid4()
    org_2 = uuid.uuid4()
    worker_1_id = uuid.uuid4()
    worker_2_id = uuid.uuid4()

    worker_1 = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=org_1,
        email="w1@amap.org",
        full_name="Worker 1",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=worker_1_id,
    )

    dummy_app.dependency_overrides[get_current_user] = lambda: worker_1
    try:
        # Same org -> 200
        resp = client.get(f"/protected/org/{org_1}")
        assert resp.status_code == status.HTTP_200_OK

        # Other org -> 403 Forbidden
        resp = client.get(f"/protected/org/{org_2}")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Self worker profile -> 200
        resp = client.get(f"/protected/worker/{worker_1_id}")
        assert resp.status_code == status.HTTP_200_OK

        # Other worker profile -> 403 Forbidden
        resp = client.get(f"/protected/worker/{worker_2_id}")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        dummy_app.dependency_overrides.clear()
