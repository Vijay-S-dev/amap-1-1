"""Phase 5 department CRUD integration tests (real PostgreSQL, real API path).

Covers:
- List: aggregate counts (supervisor/worker/active tasks) are computed from
  PostgreSQL, not the hardcoded supervisor=1/worker=2/tasks=1 constants.
- Create: persists a real row; duplicate name -> HTTP 409 (DB-enforced).
- Update: rename/status changes actually persist (previously audit-only).
- Deactivate: flips department status to inactive in PostgreSQL
  (previously audit-only fake success).
- Tenant isolation and honesty of every returned count.
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
def created_department(admin_token, client):
    name = f"Phase 5 Dept {uuid4().hex[:6]}"
    resp = client.post(
        "/api/v1/organizations/manage/departments",
        headers=_auth(admin_token),
        json={"name": name, "status": "active"},
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()
    try:
        yield {"name": name, "response": body}
    finally:
        _pg("DELETE FROM audit_events WHERE resource_id = %s", (body["id"],))
        _pg("DELETE FROM departments WHERE id = %s", (body["id"],))


def test_list_departments_counts_are_database_derived(client, admin_token):
    """Read: every count matches an independent SQL computation."""
    resp = client.get(
        "/api/v1/organizations/manage/departments", headers=_auth(admin_token)
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    items = resp.json()
    assert len(items) >= 1

    for item in items:
        # Independent recomputation of worker_count
        db_workers = _pg(
            """
            SELECT COUNT(DISTINCT wp.id)
            FROM worker_profiles wp
            JOIN users u ON u.id = wp.user_id
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id AND r.name = 'worker'
            JOIN user_departments ud ON ud.user_id = u.id
            WHERE ud.department_id = %s AND u.status = 'active' AND wp.status = 'active'
            """,
            (item["id"],),
        )[0][0]
        assert item["worker_count"] == db_workers, (
            f"{item['name']}: API worker_count={item['worker_count']} "
            f"but database says {db_workers}"
        )

        db_supervisors = _pg(
            """
            SELECT COUNT(*)
            FROM user_departments ud
            JOIN user_roles ur ON ur.user_id = ud.user_id
            JOIN roles r ON r.id = ur.role_id AND r.name = 'supervisor'
            WHERE ud.department_id = %s
            """,
            (item["id"],),
        )[0][0]
        assert item["supervisor_count"] == db_supervisors

    # The seed has NO user-department links, so the historical hardcoded
    # (1 supervisor, 2 workers, 1 task) values must NOT reappear.
    for item in items:
        assert (item["supervisor_count"], item["worker_count"], item["active_tasks_count"]) != (1, 2, 1)


def test_counts_change_after_real_assignment(client, admin_token, created_department):
    """Read: inviting a worker into a department bumps its worker_count for real."""
    dept_id = created_department["response"]["id"]
    baseline = next(
        d for d in client.get(
            "/api/v1/organizations/manage/departments", headers=_auth(admin_token)
        ).json()
        if d["id"] == dept_id
    )
    assert baseline["worker_count"] == 0

    email = f"phase5-{uuid4().hex[:8]}@amap.com"
    invite = client.post(
        "/api/v1/organizations/manage/workers/invite",
        headers=_auth(admin_token),
        json={
            "email": email,
            "full_name": "Phase Five Worker",
            "department_id": dept_id,
        },
    )
    assert invite.status_code == status.HTTP_201_CREATED, invite.text
    user_id = invite.json()["user_id"]
    try:
        after = next(
            d for d in client.get(
                "/api/v1/organizations/manage/departments", headers=_auth(admin_token)
            ).json()
            if d["id"] == dept_id
        )
        assert after["worker_count"] == 1, "worker_count must reflect the new member"
    finally:
        _pg("DELETE FROM worker_readiness WHERE worker_profile_id = %s",
            (invite.json()["worker_profile_id"],))
        _pg("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
        _pg("DELETE FROM user_departments WHERE user_id = %s", (user_id,))
        _pg("DELETE FROM audit_events WHERE resource_id = %s",
            (invite.json()["worker_profile_id"],))
        _pg("DELETE FROM worker_profiles WHERE id = %s",
            (invite.json()["worker_profile_id"],))
        _pg("DELETE FROM users WHERE id = %s", (user_id,))


def test_create_department_persists_and_duplicates_conflict(
    client, admin_token, created_department
):
    """Create: row exists in PostgreSQL; duplicate name -> 409 (was 400)."""
    dept_id = created_department["response"]["id"]
    row = _pg("SELECT name, status FROM departments WHERE id = %s", (dept_id,))
    assert row and row[0][0] == created_department["name"] and row[0][1] == "active"

    dup = client.post(
        "/api/v1/organizations/manage/departments",
        headers=_auth(admin_token),
        json={"name": created_department["name"]},  # exact duplicate
    )
    assert dup.status_code == status.HTTP_409_CONFLICT, dup.text

    # Case-variant duplicates are also rejected
    dup2 = client.post(
        "/api/v1/organizations/manage/departments",
        headers=_auth(admin_token),
        json={"name": created_department["name"].upper()},
    )
    assert dup2.status_code == status.HTTP_409_CONFLICT, dup2.text

    count = _pg(
        "SELECT COUNT(*) FROM departments WHERE organization_id = %s AND lower(name) = lower(%s)",
        (ORG_A, created_department["name"]),
    )
    assert count[0][0] == 1


def test_update_department_persists_rename_and_status(
    client, admin_token, created_department
):
    """Update: PUT actually persists (previously returned payload values without
    writing anything to the database)."""
    dept_id = created_department["response"]["id"]
    new_name = f"{created_department['name']} Renamed"

    resp = client.put(
        f"/api/v1/organizations/manage/departments/{dept_id}",
        headers=_auth(admin_token),
        json={"name": new_name, "status": "archived"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["name"] == new_name
    assert body["status"] == "archived"

    row = _pg("SELECT name, status FROM departments WHERE id = %s", (dept_id,))
    assert row[0][0] == new_name, "rename not persisted"
    assert row[0][1] == "archived", "status change not persisted"

    # Rename to an existing department name -> 409
    other = client.post(
        "/api/v1/organizations/manage/departments",
        headers=_auth(admin_token),
        json={"name": f"Phase 5 Conflict {uuid4().hex[:6]}"},
    )
    assert other.status_code == status.HTTP_201_CREATED
    try:
        conflict = client.put(
            f"/api/v1/organizations/manage/departments/{dept_id}",
            headers=_auth(admin_token),
            json={"name": other.json()["name"]},
        )
        assert conflict.status_code == status.HTTP_409_CONFLICT, conflict.text
    finally:
        _pg("DELETE FROM audit_events WHERE resource_id = %s", (other.json()["id"],))
        _pg("DELETE FROM departments WHERE id = %s", (other.json()["id"],))


def test_deactivate_department_persists_status(client, admin_token, created_department):
    """Deactivate: DELETE flips status to inactive in PostgreSQL (audit-only no more)."""
    dept_id = created_department["response"]["id"]

    resp = client.delete(
        f"/api/v1/organizations/manage/departments/{dept_id}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["status"] == "inactive"

    row = _pg("SELECT status FROM departments WHERE id = %s", (dept_id,))
    assert row[0][0] == "inactive", "deactivation not persisted"

    listing = client.get(
        "/api/v1/organizations/manage/departments", headers=_auth(admin_token)
    ).json()
    match = [d for d in listing if d["id"] == dept_id]
    assert match and match[0]["status"] == "inactive"

    audit = _pg(
        "SELECT event_type FROM audit_events WHERE resource_id = %s", (dept_id,)
    )
    assert any(a[0] == "department.deactivated" for a in audit)

    # Idempotent second deactivate still succeeds and does not duplicate audit rows
    resp2 = client.delete(
        f"/api/v1/organizations/manage/departments/{dept_id}",
        headers=_auth(admin_token),
    )
    assert resp2.status_code == status.HTTP_200_OK
    audit_count = _pg(
        "SELECT COUNT(*) FROM audit_events WHERE resource_id = %s AND event_type = 'department.deactivated'",
        (dept_id,),
    )
    assert audit_count[0][0] == 1


def test_department_404_semantics(client, admin_token):
    """Update/deactivate of unknown or cross-tenant departments -> 404."""
    resp = client.put(
        f"/api/v1/organizations/manage/departments/{uuid4()}",
        headers=_auth(admin_token),
        json={"name": "Ghost"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    resp = client.delete(
        f"/api/v1/organizations/manage/departments/{uuid4()}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Cross-tenant: Org B department cannot be mutated by Org A admin
    org_b_dept = str(uuid4())
    _pg(
        "INSERT INTO organizations (id, name, status) VALUES (%s, 'Phase 5 Tenant B', 'active') "
        "ON CONFLICT (id) DO NOTHING",
        (ORG_B,),
    )
    _pg(
        "INSERT INTO departments (id, organization_id, name, status) VALUES (%s, %s, 'B Dept', 'active')",
        (org_b_dept, ORG_B),
    )
    try:
        resp = client.put(
            f"/api/v1/organizations/manage/departments/{org_b_dept}",
            headers=_auth(admin_token),
            json={"name": "Hijacked"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        row = _pg("SELECT name FROM departments WHERE id = %s", (org_b_dept,))
        assert row[0][0] == "B Dept", "cross-tenant department was mutated!"
    finally:
        _pg("DELETE FROM departments WHERE id = %s", (org_b_dept,))
        _pg("DELETE FROM organizations WHERE id = %s", (ORG_B,))


def test_update_department_empty_payload_400(client, admin_token, created_department):
    """Update: empty payload -> 400 instead of audit-only fake success."""
    resp = client.put(
        f"/api/v1/organizations/manage/departments/{created_department['response']['id']}",
        headers=_auth(admin_token),
        json={},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
