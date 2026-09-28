"""Phase 3 worker CRUD integration tests (real PostgreSQL, real API path).

Covers the binding Definition of Done for worker management:
- Create: invite persists user + worker profile + department + role + readiness rows.
- Read: list_workers returns real rows (no hardcoded roster), with derived status.
- Duplicate email -> HTTP 409.
- Update/Deactivate: suspending/archiving a user flips them to DEACTIVATED.
- Refresh persistence: new service instances and repeated calls read the same rows.
- Tenant isolation: other organizations' workers never appear.
"""

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG_A = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ORG_B = "8b52d14c-6b21-4001-8b06-0722c6a31e54"
DEFAULT_PASSWORD = "SecurePassword123!"


@pytest.fixture()
def client():
    """Real auth path client; logged in as the seeded org admin."""
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": ORG_A,
            "email": "admin@amap.com",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _pg(sql, params=None):
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


@pytest.fixture()
def invited_worker(admin_token, client):
    """Invite a fresh worker and yield (payload_email, created user_id, profile_id)."""
    email = f"phase3-{uuid4().hex[:10]}@amap.com"
    resp = client.post(
        "/api/v1/organizations/manage/workers/invite",
        headers=_auth(admin_token),
        json={
            "email": email,
            "full_name": "Phase Three Worker",
            "badge_number": f"WRK-{uuid4().hex[:4].upper()}",
            "preferred_modality": "gesture",
            "temporary_password": "TempInvite123!",
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()
    try:
        yield {"email": email, "response": body}
    finally:
        _pg("DELETE FROM worker_readiness WHERE worker_profile_id = %s", (body["worker_profile_id"],))
        _pg("DELETE FROM user_roles WHERE user_id = %s", (body["user_id"],))
        _pg("DELETE FROM user_departments WHERE user_id = %s", (body["user_id"],))
        _pg("DELETE FROM worker_profiles WHERE id = %s", (body["worker_profile_id"],))
        _pg("DELETE FROM audit_events WHERE resource_id = %s", (body["worker_profile_id"],))
        _pg("DELETE FROM users WHERE id = %s", (body["user_id"],))


def test_invite_creates_real_rows_in_postgres(client, admin_token, invited_worker):
    """Create: every relationship row must exist with the IDs returned by the API."""
    body = invited_worker["response"]
    user_id = body["user_id"]
    profile_id = body["worker_profile_id"]

    users = _pg("SELECT id, email, status FROM users WHERE id = %s", (user_id,))
    assert users and users[0][1] == invited_worker["email"] and users[0][2] == "active"

    profiles = _pg(
        "SELECT id, user_id, badge_number, status FROM worker_profiles WHERE id = %s",
        (profile_id,),
    )
    assert profiles and str(profiles[0][1]) == str(user_id)
    assert profiles[0][3] == "active"

    roles = _pg(
        "SELECT r.name FROM user_roles ur JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = %s",
        (user_id,),
    )
    assert roles and roles[0][0] == "worker"

    readiness = _pg(
        "SELECT interaction_mode, readiness_status FROM worker_readiness WHERE worker_profile_id = %s",
        (profile_id,),
    )
    assert readiness, "invite must persist readiness preferences"
    assert readiness[0][0] == "gesture"
    assert readiness[0][1] == "incomplete"

    audit = _pg(
        "SELECT event_type FROM audit_events WHERE resource_id = %s", (profile_id,)
    )
    assert audit and audit[0][0] == "worker.invited"


def test_invite_duplicate_email_returns_409(client, admin_token, invited_worker):
    """Create: duplicate email within the organization -> 409 Conflict."""
    resp = client.post(
        "/api/v1/organizations/manage/workers/invite",
        headers=_auth(admin_token),
        json={
            "email": invited_worker["email"].upper(),  # case-insensitive dup
            "full_name": "Duplicate Person",
        },
    )
    assert resp.status_code == status.HTTP_409_CONFLICT, resp.text

    # Exactly one account exists for that email
    rows = _pg(
        "SELECT COUNT(*) FROM users WHERE organization_id = %s AND lower(email) = lower(%s)",
        (ORG_A, invited_worker["email"]),
    )
    assert rows[0][0] == 1


def test_list_workers_returns_real_rows_not_hardcoded_roster(
    client, admin_token, invited_worker
):
    """Read: list contains the invited worker + seeded workers, never the old
    fabricated roster (Samira Chen / Kenji Sato never existed in PostgreSQL)."""
    resp = client.get(
        "/api/v1/organizations/manage/workers?page=1&page_size=100",
        headers=_auth(admin_token),
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    emails = [item["email"] for item in data["items"]]
    assert invited_worker["email"] in emails, "invited worker missing from real list"
    assert "alex.worker@amap.com" in emails
    assert "jordan.worker@amap.com" in emails

    fabricated = {"samira.chen@amap.com", "kenji.sato@amap.com"}
    assert not fabricated & set(emails), "hardcoded fake roster leaked into response"

    # Total must match the actual PostgreSQL worker-profile count for this org
    db_count = _pg(
        """
        SELECT COUNT(*)
        FROM worker_profiles wp
        JOIN users u ON u.id = wp.user_id
        WHERE u.organization_id = %s
          AND u.status NOT IN ('archived', 'suspended', 'inactive')
          AND wp.status = 'active'
        """,
        (ORG_A,),
    )[0][0]
    assert data["total_count"] == db_count

    # IDs are real: every listed worker_profile_id resolves to a DB row
    for item in data["items"]:
        row = _pg(
            "SELECT user_id FROM worker_profiles WHERE id = %s",
            (item["worker_profile_id"],),
        )
        assert row, f"list item {item['worker_profile_id']} has no PostgreSQL row"


def test_list_workers_pagination_and_status_filter(client, admin_token, invited_worker):
    """Read: pagination metadata and status filtering operate on real rows."""
    resp = client.get(
        "/api/v1/organizations/manage/workers?page=1&page_size=1&status=INVITED",
        headers=_auth(admin_token),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) <= 1
    for item in data["items"]:
        assert item["status"] == "INVITED"


def test_invited_worker_can_login_and_data_persists(client, admin_token, invited_worker):
    """Create -> auth -> read: the invited worker's own credentials work and
    their profile survives a fresh login (persistence across sessions)."""
    email = invited_worker["email"]
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": ORG_A,
            "email": email,
            "password": "TempInvite123!",
        },
    )
    assert login.status_code == status.HTTP_200_OK, login.text
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == status.HTTP_200_OK
    profile = me.json()
    assert profile["email"] == email
    assert profile["roles"] == ["worker"]
    assert profile["worker_profile_id"] is not None

    # Second session: logout-equivalent (new login) still resolves same profile
    login2 = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": ORG_A,
            "email": email,
            "password": "TempInvite123!",
        },
    )
    assert login2.status_code == status.HTTP_200_OK
    me2 = client.get("/api/v1/auth/me", headers=_auth(login2.json()["access_token"]))
    assert me2.json()["worker_profile_id"] == profile["worker_profile_id"]


def test_deactivate_worker_reflects_in_directory(client, admin_token, invited_worker):
    """Update/Deactivate: suspending the user flips the directory status to
    DEACTIVATED (previously an API 500: users.status CHECK rejected 'suspended')."""
    body = invited_worker["response"]
    user_id = body["user_id"]

    resp = client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers=_auth(admin_token),
        json={"status": "suspended", "reason": "Phase 3 deactivation check"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["status"] == "suspended"

    # Persisted in PostgreSQL
    row = _pg("SELECT status FROM users WHERE id = %s", (user_id,))
    assert row[0][0] == "suspended"

    # Directory reflects it
    listing = client.get(
        "/api/v1/organizations/manage/workers?page=1&page_size=100",
        headers=_auth(admin_token),
    )
    assert listing.status_code == status.HTTP_200_OK
    match = [
        item
        for item in listing.json()["items"]
        if item["user_id"] == str(user_id)
    ]
    assert match, "deactivated worker must remain visible in directory"
    assert match[0]["status"] == "DEACTIVATED"


def test_directory_is_tenant_isolated(client, admin_token, invited_worker):
    """Read: a different organization's user never appears in org A's directory."""
    other_user_id = str(uuid4())
    _pg(
        "INSERT INTO organizations (id, name, status) VALUES (%s, 'Phase 3 Tenant B', 'active') "
        "ON CONFLICT (id) DO NOTHING",
        (ORG_B,),
    )
    _pg(
        """
        INSERT INTO users (id, organization_id, email, full_name, password_hash, status)
        VALUES (%s, %s, %s, 'Other Tenant', 'x', 'active')
        """,
        (other_user_id, ORG_B, f"other-{uuid4().hex[:8]}@amap.com"),
    )
    try:
        resp = client.get(
            "/api/v1/organizations/manage/workers?page=1&page_size=100",
            headers=_auth(admin_token),
        )
        assert resp.status_code == status.HTTP_200_OK
        emails = [item["email"] for item in resp.json()["items"]]
        assert not any(e.startswith("other-") for e in emails)
        user_ids = [item["user_id"] for item in resp.json()["items"]]
        assert other_user_id not in user_ids
    finally:
        _pg("DELETE FROM users WHERE id = %s", (other_user_id,))
        _pg("DELETE FROM organizations WHERE id = %s", (ORG_B,))


def test_list_workers_survives_service_reinstantiation(client, admin_token, invited_worker):
    """Refresh persistence: a brand-new service instance reads the same rows
    (no in-memory caching of the directory)."""
    from services.organization_management_service import OrganizationManagementService
    from uuid import UUID

    service = OrganizationManagementService()
    rows, total = service.workers_repo.list_enterprise_directory(
        organization_id=UUID(ORG_A), limit=100, offset=0
    )
    emails = [r["email"] for r in rows]
    assert invited_worker["email"] in emails
    assert total >= len(rows)
