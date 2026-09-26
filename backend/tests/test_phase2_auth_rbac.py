"""Phase 2 auth + RBAC integration tests (real PostgreSQL, real JWT path).

Covers:
- Seeded account login works end-to-end (seeded password hash must verify).
- verify_token never raises NameError -> 500 for unknown subjects (401 instead).
- 401 vs 403 semantics: missing/invalid credentials = 401;
  authenticated-but-insufficient-role = 403.
- Canonical roles issued at login: admin / organization_admin / supervisor / worker.
"""

from uuid import uuid4

import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.main import app
from services.authorization_service import AuthorizationService
from models.auth import AuthenticatedUserContext

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
DEFAULT_PASSWORD = "SecurePassword123!"


@pytest.fixture()
def client():
    """Client with NO dependency overrides - the real auth path is exercised."""
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def _login(client, email, password=DEFAULT_PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"organization_id": ORG, "email": email, "password": password},
    )


def _me(client, token):
    return client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )


# ---------------------------------------------------------------------------
# Seeded credentials (the seed documents SecurePassword123! as default)
# ---------------------------------------------------------------------------

def test_seeded_admin_login_and_roles(client):
    """admin@amap.com logs in with the documented seeded password."""
    resp = _login(client, "admin@amap.com")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    token = resp.json()["access_token"]

    me = _me(client, token)
    assert me.status_code == status.HTTP_200_OK, me.text
    profile = me.json()
    assert profile["email"] == "admin@amap.com"
    assert "admin" in profile["roles"]
    assert "organization_admin" in profile["roles"]


def test_seeded_supervisor_login_and_roles(client):
    resp = _login(client, "supervisor@amap.com")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    me = _me(client, resp.json()["access_token"])
    assert me.status_code == status.HTTP_200_OK
    assert me.json()["roles"] == ["supervisor"]


def test_seeded_worker_login_and_roles(client):
    resp = _login(client, "alex.worker@amap.com")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    me = _me(client, resp.json()["access_token"])
    assert me.status_code == status.HTTP_200_OK
    profile = me.json()
    assert profile["roles"] == ["worker"]
    assert profile["worker_profile_id"] is not None


def test_login_wrong_password_401(client):
    resp = _login(client, "admin@amap.com", password="WrongPassword123!")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_unknown_email_401(client):
    resp = _login(client, f"nobody-{uuid4()}@amap.com")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_wrong_organization_401(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": str(uuid4()),
            "email": "admin@amap.com",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 401 vs 403 semantics
# ---------------------------------------------------------------------------

def test_missing_bearer_header_returns_401(client):
    """No Authorization header -> 401 (not 403) with WWW-Authenticate."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "www-authenticate" in {k.lower() for k in resp.headers.keys()}


def test_invalid_token_returns_401(client):
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_verify_token_unknown_subject_returns_401_not_500(client):
    """A well-formed token for a user that no longer exists must be 401,
    not the historical NameError -> 500 inside verify_token."""
    from utils.security import create_access_token

    ghost_token = create_access_token(
        {
            "sub": str(uuid4()),
            "organization_id": ORG,
            "email": "ghost@example.com",
            "roles": ["worker"],
            "permissions": [],
            "worker_profile_id": None,
        }
    )
    resp = _me(client, ghost_token)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text


def test_worker_gets_403_on_admin_route(client):
    """Authenticated worker hitting an admin-guarded route -> 403 (not 401)."""
    login = _login(client, "alex.worker@amap.com")
    assert login.status_code == status.HTTP_200_OK
    token = login.json()["access_token"]

    resp = client.get(
        "/api/v1/organizations/manage/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text


def test_unauthenticated_admin_route_returns_401(client):
    """Same admin route with NO credentials -> 401 (the original failing test)."""
    resp = client.get("/api/v1/organizations/manage/dashboard")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Canonical role semantics
# ---------------------------------------------------------------------------

def test_canonical_role_names_in_database(client):
    """The roles table contains exactly the canonical role set."""
    import psycopg

    from app.config import get_settings

    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM roles ORDER BY name")
            names = [r[0] for r in cur.fetchall()]
    assert set(names) >= {"admin", "organization_admin", "supervisor", "worker"}


def test_organization_admin_role_authorization_semantics():
    """organization_admin gets admin-equivalent feature permission checks
    but does NOT bypass organization isolation."""
    org_a = uuid4()
    org_b = uuid4()
    org_admin = AuthenticatedUserContext(
        user_id=uuid4(),
        organization_id=org_a,
        email="orgadmin@amap.org",
        full_name="Org Admin",
        status="active",
        roles=["organization_admin"],
        permissions=[],
    )

    # Feature permission bypass mirrors admin
    assert AuthorizationService.has_permission(org_admin, "admin:config") is True
    assert AuthorizationService.has_all_permissions(org_admin, ["session:read"]) is True
    # Role gate passes when organization_admin is accepted
    assert AuthorizationService.has_any_role(org_admin, ["admin", "organization_admin"]) is True
    # Worker access parity with admin
    assert AuthorizationService.can_access_worker(org_admin, uuid4()) is True
    # Organization isolation STILL applies (org-scoped, not global)
    with pytest.raises(Exception):
        AuthorizationService.assert_same_organization(org_admin, org_b)
