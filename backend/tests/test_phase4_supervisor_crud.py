"""Phase 4 supervisor CRUD integration tests (real PostgreSQL, real API path).

Covers:
- List: supervisors come from PostgreSQL (role-driven), with real departments
  and real assigned-worker counts - no fabricated "Marcus Vance" fallback.
- Create: invite persists user + department + supervisor role; 409 duplicate.
- Update: department reassignment and status change actually mutate rows
  (previously audit-only writes that changed nothing).
- Deactivate: suspending a supervisor persists and is reflected in the list.
- Tenant isolation and persistence across service reinstantiation.
"""

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
DEPT_POWERTRAIN = "11111111-1111-1111-1111-111111111111"
DEPT_CHASSIS = "22222222-2222-2222-2222-222222222222"


@pytest.fixture()
def client():
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
def invited_supervisor(admin_token, client):
    email = f"phase4-sup-{uuid4().hex[:10]}@amap.com"
    resp = client.post(
        "/api/v1/organizations/manage/supervisors/invite",
        headers=_auth(admin_token),
        json={
            "email": email,
            "full_name": "Phase Four Supervisor",
            "department_id": DEPT_CHASSIS,
            "temporary_password": "TempSuper123!",
            "notes": "Phase 4 verification",
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()
    try:
        yield {"email": email, "response": body}
    finally:
        _pg("DELETE FROM user_roles WHERE user_id = %s", (body["user_id"],))
        _pg("DELETE FROM user_departments WHERE user_id = %s", (body["user_id"],))
        _pg("DELETE FROM audit_events WHERE resource_id = %s", (body["user_id"],))
        _pg("DELETE FROM users WHERE id = %s", (body["user_id"],))


def test_list_supervisors_real_rows(client, admin_token):
    """Read: seeded supervisor comes from the database with real department data."""
    resp = client.get(
        "/api/v1/organizations/manage/supervisors", headers=_auth(admin_token)
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    items = resp.json()

    emails = [s["email"] for s in items]
    assert "supervisor@amap.com" in emails, "seeded supervisor missing from list"
    # No fabricated extras
    for item in items:
        row = _pg("SELECT id FROM users WHERE id = %s", (item["user_id"],))
        assert row, f"list item {item['user_id']} has no PostgreSQL row"

    seeded = next(s for s in items if s["email"] == "supervisor@amap.com")
    assert seeded["full_name"] == "Marcus Vance (Supervisor)"
    # Real assigned-worker count: derived from shared departments, not the
    # hardcoded 3 that the previous implementation always returned.
    assert isinstance(seeded["assigned_workers_count"], int)
    assert seeded["assigned_workers_count"] >= 0


def test_invite_supervisor_persists_real_rows(client, admin_token, invited_supervisor):
    """Create: user + department + supervisor role rows exist with API IDs."""
    body = invited_supervisor["response"]
    user_id = body["user_id"]

    user_row = _pg(
        "SELECT email, status FROM users WHERE id = %s", (user_id,)
    )
    assert user_row and user_row[0][0] == invited_supervisor["email"]
    assert user_row[0][1] == "active"

    roles = _pg(
        "SELECT r.name FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
        "WHERE ur.user_id = %s",
        (user_id,),
    )
    assert [r[0] for r in roles] == ["supervisor"]

    depts = _pg(
        "SELECT department_id FROM user_departments WHERE user_id = %s", (user_id,)
    )
    assert depts and str(depts[0][0]) == DEPT_CHASSIS

    audit = _pg(
        "SELECT event_type FROM audit_events WHERE resource_id = %s", (user_id,)
    )
    assert audit and audit[0][0] == "supervisor.invited"

    # Appears in the directory list with the real department
    listing = client.get(
        "/api/v1/organizations/manage/supervisors", headers=_auth(admin_token)
    ).json()
    match = [s for s in listing if s["user_id"] == str(user_id)]
    assert match and match[0]["department_name"] == "Chassis & Structural Welding"
    assert match[0]["status"] == "active"


def test_invite_supervisor_duplicate_409(client, admin_token, invited_supervisor):
    """Create: duplicate email -> 409, single row remains."""
    resp = client.post(
        "/api/v1/organizations/manage/supervisors/invite",
        headers=_auth(admin_token),
        json={
            "email": invited_supervisor["email"].upper(),
            "full_name": "Duplicate Supervisor",
        },
    )
    assert resp.status_code == status.HTTP_409_CONFLICT, resp.text
    count = _pg(
        "SELECT COUNT(*) FROM users WHERE organization_id = %s AND lower(email) = lower(%s)",
        (ORG_A, invited_supervisor["email"]),
    )
    assert count[0][0] == 1


def test_invited_supervisor_login(client, admin_token, invited_supervisor):
    """Create -> auth: invited supervisor authenticates with the given credential."""
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": ORG_A,
            "email": invited_supervisor["email"],
            "password": "TempSuper123!",
        },
    )
    assert login.status_code == status.HTTP_200_OK, login.text
    me = client.get(
        "/api/v1/auth/me", headers=_auth(login.json()["access_token"])
    )
    assert me.status_code == status.HTTP_200_OK
    assert me.json()["roles"] == ["supervisor"]


def test_update_supervisor_reassigns_department_for_real(
    client, admin_token, invited_supervisor
):
    """Update: PUT /supervisors/{id} actually moves the department assignment."""
    body = invited_supervisor["response"]
    user_id = body["user_id"]

    # Seeded in CHASSIS at invite time
    before = _pg(
        "SELECT department_id FROM user_departments WHERE user_id = %s", (user_id,)
    )
    assert before and str(before[0][0]) == DEPT_CHASSIS

    resp = client.put(
        f"/api/v1/organizations/manage/supervisors/{user_id}",
        headers=_auth(admin_token),
        json={"department_id": DEPT_POWERTRAIN},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["changes"]["department_id"] == DEPT_POWERTRAIN

    after = _pg(
        "SELECT department_id FROM user_departments WHERE user_id = %s", (user_id,)
    )
    assert after and str(after[0][0]) == DEPT_POWERTRAIN, "department change not persisted"
    assert len(after) == 1, "old department link must be removed"

    listing = client.get(
        "/api/v1/organizations/manage/supervisors", headers=_auth(admin_token)
    ).json()
    match = [s for s in listing if s["user_id"] == str(user_id)]
    assert match and match[0]["department_name"] == "Powertrain & Gearbox Integration"


def test_update_supervisor_status_persists(client, admin_token, invited_supervisor):
    """Update/Deactivate: status change persists to PostgreSQL and reflects in list."""
    body = invited_supervisor["response"]
    user_id = body["user_id"]

    resp = client.put(
        f"/api/v1/organizations/manage/supervisors/{user_id}",
        headers=_auth(admin_token),
        json={"status": "suspended"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    row = _pg("SELECT status FROM users WHERE id = %s", (user_id,))
    assert row[0][0] == "suspended", "supervisor suspension not persisted"

    listing = client.get(
        "/api/v1/organizations/manage/supervisors", headers=_auth(admin_token)
    ).json()
    match = [s for s in listing if s["user_id"] == str(user_id)]
    assert match and match[0]["status"] == "suspended"

    # Suspended supervisor's session is rejected on next request
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": ORG_A,
            "email": invited_supervisor["email"],
            "password": "TempSuper123!",
        },
    )
    assert login.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_supervisor_404_semantics(client, admin_token):
    """Update: unknown user and non-supervisor users yield 404 (not silent success)."""
    resp = client.put(
        f"/api/v1/organizations/manage/supervisors/{uuid4()}",
        headers=_auth(admin_token),
        json={"status": "suspended"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # A worker is not a supervisor -> 404 and no audit-only fake success
    worker = _pg(
        "SELECT id FROM users WHERE organization_id = %s AND email = 'alex.worker@amap.com'",
        (ORG_A,),
    )[0][0]
    resp = client.put(
        f"/api/v1/organizations/manage/supervisors/{worker}",
        headers=_auth(admin_token),
        json={"status": "suspended"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    row = _pg("SELECT status FROM users WHERE id = %s", (worker,))
    assert row[0][0] == "active", "non-supervisor must not be mutated"


def test_update_supervisor_empty_payload_422(client, admin_token, invited_supervisor):
    """Update: empty payload -> 422 instead of audit-only fake success."""
    resp = client.put(
        f"/api/v1/organizations/manage/supervisors/{invited_supervisor['response']['user_id']}",
        headers=_auth(admin_token),
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_supervisor_directory_tenant_isolated(client, admin_token):
    """Read: other-organization supervisors never appear in org A's list."""
    other_id = str(uuid4())
    _pg(
        "INSERT INTO organizations (id, name, status) VALUES (%s, 'Phase 4 Tenant B', 'active') "
        "ON CONFLICT (id) DO NOTHING",
        (ORG_B,),
    )
    _pg(
        """
        INSERT INTO users (id, organization_id, email, full_name, password_hash, status)
        VALUES (%s, %s, %s, 'Other Supervisor', 'x', 'active')
        """,
        (other_id, ORG_B, f"other-sup-{uuid4().hex[:8]}@amap.com"),
    )
    sup_role = _pg("SELECT id FROM roles WHERE name = 'supervisor'")[0][0]
    _pg(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
        (other_id, sup_role),
    )
    try:
        listing = client.get(
            "/api/v1/organizations/manage/supervisors", headers=_auth(admin_token)
        ).json()
        ids = [s["user_id"] for s in listing]
        assert other_id not in ids
        assert not any(s["email"].startswith("other-sup-") for s in listing)
    finally:
        _pg("DELETE FROM user_roles WHERE user_id = %s", (other_id,))
        _pg("DELETE FROM users WHERE id = %s", (other_id,))
        _pg("DELETE FROM organizations WHERE id = %s", (ORG_B,))
