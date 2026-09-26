"""Phase 8 admin + organization management integration tests (real PostgreSQL).

Covers the known 500s and fabricated data paths:
- GET /admin/users (was AttributeError -> 500)
- GET /organizations/manage/audit (was TypeError -> 500, plus a
  fabricated 'seeded default audit stream' and hardcoded actor names)
- PUT /admin/organization (was AttributeError -> 500)
- PUT /organizations/manage/profile (was silent audit-only fake success)
- Assistance overview (was hardcoded Samira Chen / Marcus Vance rows)
- Emergencies (was hardcoded [])
- Analytics (was hardcoded 19/3/8.2/94.5/6/1.5/0 constants)
- Dashboard KPIs (were computed from a vocabulary that never matches)
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"
JORDAN = "d0000000-0000-0000-0000-000000000002"
JORDAN_USER = "c0000000-0000-0000-0000-000000000004"  # jordan.worker@amap.com
DEFAULT_PASSWORD = "SecurePassword123!"
VERIFIED_HASH = (
    "pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$"
    "10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9"
)


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _login(client, email, org=ORG):
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": org, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
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


# ---------------------------------------------------------------------------
# /admin/users (was 500)
# ---------------------------------------------------------------------------

def test_admin_users_list_matches_database(client):
    tok = _login(client, "admin@amap.com")
    res = client.get("/api/v1/admin/users", headers=_auth(tok))
    assert res.status_code == status.HTTP_200_OK, res.text
    body = res.json()
    assert len(body) >= 1

    rows = _pg("SELECT id::text, email, status FROM users WHERE organization_id = %s", (ORG,))
    db = {r[0]: r for r in rows}
    for u in body:
        assert u["id"] in db, "user must exist in PostgreSQL"
        assert u["email"] == db[u["id"]][1]
        assert u["status"] == db[u["id"]][2]
        assert "password_hash" not in u
    # exactly the org's users (no other tenant leakage)
    assert {u["id"] for u in body} == set(db.keys())


def test_admin_users_rbac(client):
    worker = _login(client, "alex.worker@amap.com")
    res = client.get("/api/v1/admin/users", headers=_auth(worker))
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text


# ---------------------------------------------------------------------------
# Audit endpoints (both were 500; org audit also fabricated actors + stream)
# ---------------------------------------------------------------------------

def test_org_audit_matches_database_with_real_actors(client):
    tok = _login(client, "admin@amap.com")
    # trigger a real audited action (profile touch)
    res = client.put(
        "/api/v1/organizations/manage/profile",
        json={"contact_email": "qa@acme.example"},
        headers=_auth(tok),
    )
    assert res.status_code == 200, res.text

    res = client.get("/api/v1/organizations/manage/audit?limit=10", headers=_auth(tok))
    assert res.status_code == status.HTTP_200_OK, res.text
    items = res.json()
    assert len(items) >= 1

    db = _pg(
        "SELECT event_type, actor_user_id FROM audit_events "
        "WHERE organization_id = %s ORDER BY occurred_at DESC LIMIT 10",
        (ORG,),
    )
    assert [i["event_type"] for i in items] == [r[0] for r in db]
    # actor identity resolved from users/roles, not fabricated "Administrator"
    profile_events = [i for i in items if i["event_type"] == "organization.profile_updated"]
    assert profile_events, "our action must be in the trail"
    assert profile_events[0]["actor_name"] == "Sarah Jenkins (Admin)"
    assert profile_events[0]["actor_role"] in ("admin", "organization_admin")

    # admin audit-logs endpoint (real rows, limit honored)
    res = client.get("/api/v1/admin/audit-logs?limit=5", headers=_auth(tok))
    assert res.status_code == 200, res.text
    assert 1 <= len(res.json()) <= 5
    res = client.get("/api/v1/admin/audit-logs?event_type=organization.profile_updated",
                     headers=_auth(tok))
    assert res.status_code == 200
    assert all(i["event_type"] == "organization.profile_updated" for i in res.json())


def test_org_audit_empty_trail_is_empty_not_fabricated(client):
    """A brand-new tenant with no audit rows must see [], not a seeded stream."""
    org_id, user_id = str(uuid4()), str(uuid4())
    email = f"audit-{uuid4().hex[:8]}@example.com"
    _pg("INSERT INTO organizations (id, name, status) VALUES (%s, %s, 'active')",
        (org_id, f"P8 audit org {uuid4().hex[:6]}"))
    _pg(
        "INSERT INTO users (id, organization_id, email, full_name, password_hash, status) "
        "VALUES (%s, %s, %s, 'Audit Admin', %s, 'active')",
        (user_id, org_id, email, VERIFIED_HASH),
    )
    role_id = _pg("SELECT id FROM roles WHERE name = 'admin'")[0][0]
    _pg("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role_id))
    try:
        tok = _login(client, email, org=org_id)
        res = client.get("/api/v1/organizations/manage/audit", headers=_auth(tok))
        assert res.status_code == 200, res.text
        assert res.json() == [], "empty trail must be empty (no fabricated stream)"
    finally:
        _pg("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
        _pg("DELETE FROM users WHERE id = %s", (user_id,))
        _pg("DELETE FROM organizations WHERE id = %s", (org_id,))


# ---------------------------------------------------------------------------
# Organization profile/settings (was fabricated read + audit-only write)
# ---------------------------------------------------------------------------

def test_profile_settings_persist_all_fields(client):
    tok = _login(client, "admin@amap.com")
    # capture original row to restore afterwards
    original = _pg(
        "SELECT name, organization_type, industry, location, contact_email, "
        "default_language, supported_languages::text, accessibility_defaults::text "
        "FROM organizations WHERE id = %s",
        (ORG,),
    )[0]
    payload = {
        "organization_type": "precision_assembly",
        "industry": "EV Powertrain",
        "location": "Plant 7 — Chennai",
        "contact_email": "plant7@acme.example",
        "default_language": "en",
        "supported_languages": ["en", "hi"],
        "accessibility_defaults": {
            "default_dwell_time_ms": 750,
            "high_contrast_default": True,
            "min_target_size_px": 56,
            "voice_confirmation_default": True,
        },
    }
    try:
        res = client.put("/api/v1/organizations/manage/profile", json=payload,
                         headers=_auth(tok))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["industry"] == "EV Powertrain"
        assert body["accessibility_defaults"]["high_contrast_default"] is True

        row = _pg(
            "SELECT industry, location, contact_email, default_language, "
            "supported_languages::text, accessibility_defaults::text "
            "FROM organizations WHERE id = %s",
            (ORG,),
        )[0]
        assert row[0] == "EV Powertrain"
        assert row[1] == "Plant 7 — Chennai"
        assert row[2] == "plant7@acme.example"
        assert row[3] == "en"
        import json as _json
        assert _json.loads(row[4]) == ["en", "hi"]
        acc = _json.loads(row[5])
        assert acc["default_dwell_time_ms"] == 750
        assert acc["high_contrast_default"] is True
        assert acc["min_target_size_px"] == 56

        # refresh persistence: fresh GET
        res = client.get("/api/v1/organizations/manage/profile", headers=_auth(tok))
        assert res.json()["contact_email"] == "plant7@acme.example"
        # re-login persistence: brand-new token
        tok2 = _login(client, "admin@amap.com")
        res = client.get("/api/v1/organizations/manage/profile", headers=_auth(tok2))
        assert res.json()["location"] == "Plant 7 — Chennai"
    finally:
        _pg(
            "UPDATE organizations SET name=%s, organization_type=%s, industry=%s, "
            "location=%s, contact_email=%s, default_language=%s, "
            "supported_languages=%s::jsonb, accessibility_defaults=%s::jsonb, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (original[0], original[1], original[2], original[3], original[4],
             original[5], original[6], original[7], ORG),
        )


def test_profile_name_change_actually_persists(client):
    """The old implementation swallowed the name update (except: pass)."""
    tok = _login(client, "admin@amap.com")
    original = _pg("SELECT name FROM organizations WHERE id = %s", (ORG,))[0][0]
    new_name = f"P8 Renamed {uuid4().hex[:6]}"
    try:
        res = client.put("/api/v1/organizations/manage/profile",
                         json={"name": new_name}, headers=_auth(tok))
        assert res.status_code == 200, res.text
        row = _pg("SELECT name FROM organizations WHERE id = %s", (ORG,))
        assert row[0][0] == new_name, "rename must be written to PostgreSQL"
        # visible on admin org endpoint too (fresh read)
        res = client.get("/api/v1/admin/organization", headers=_auth(tok))
        assert res.json()["name"] == new_name
    finally:
        _pg("UPDATE organizations SET name=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (original, ORG))


def test_profile_name_conflict_409_and_invalid_inputs(client):
    tok = _login(client, "admin@amap.com")
    other = str(uuid4())
    _pg("INSERT INTO organizations (id, name, status) VALUES (%s, %s, 'active')",
        (other, "Taken Org Name P8"))
    try:
        res = client.put("/api/v1/organizations/manage/profile",
                         json={"name": "Taken Org Name P8"}, headers=_auth(tok))
        assert res.status_code == status.HTTP_409_CONFLICT, res.text
        row = _pg("SELECT name FROM organizations WHERE id = %s", (ORG,))
        assert row[0][0] != "Taken Org Name P8"  # unchanged

        res = client.put("/api/v1/organizations/manage/profile",
                         json={"name": ""}, headers=_auth(tok))
        assert res.status_code == 422  # pydantic min_length

        res = client.put("/api/v1/organizations/manage/profile",
                         json={"supported_languages": []}, headers=_auth(tok))
        assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text
    finally:
        _pg("DELETE FROM organizations WHERE id = %s", (other,))


def test_admin_organization_update_persists(client):
    """PUT /admin/organization was a 500 (orgs_repo.update missing)."""
    tok = _login(client, "admin@amap.com")
    original = _pg("SELECT name, status FROM organizations WHERE id = %s", (ORG,))[0]
    try:
        res = client.put("/api/v1/admin/organization",
                         json={"status": "inactive"}, headers=_auth(tok))
        assert res.status_code == 200, res.text
        row = _pg("SELECT status FROM organizations WHERE id = %s", (ORG,))
        assert row[0][0] == "inactive"
        res = client.get("/api/v1/admin/organization", headers=_auth(tok))
        assert res.json()["status"] == "inactive"
    finally:
        _pg("UPDATE organizations SET name=%s, status=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=%s", (original[0], original[1], ORG))


def test_admin_user_status_update_persists(client):
    tok = _login(client, "admin@amap.com")
    original = _pg("SELECT status FROM users WHERE id = %s", (JORDAN_USER,))[0][0]
    try:
        res = client.patch(f"/api/v1/admin/users/{JORDAN_USER}/status",
                           json={"status": "suspended", "reason": "phase8 test"},
                           headers=_auth(tok))
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "suspended"
        row = _pg("SELECT status FROM users WHERE id = %s", (JORDAN_USER,))
        assert row[0][0] == "suspended"
        audit = _pg(
            "SELECT 1 FROM audit_events WHERE resource_id = %s "
            "AND event_type = 'user.status_updated'",
            (JORDAN_USER,),
        )
        assert audit
        # cross-tenant user not addressable
        outsider = str(uuid4())
        _pg("INSERT INTO organizations (id, name, status) VALUES (%s, %s, 'active')",
            (outsider, f"P8 org {uuid4().hex[:6]}"))
        try:
            res = client.patch(f"/api/v1/admin/users/{outsider}/status",
                               json={"status": "suspended"}, headers=_auth(tok))
            assert res.status_code == status.HTTP_404_NOT_FOUND, res.text
        finally:
            _pg("DELETE FROM organizations WHERE id = %s", (outsider,))
    finally:
        _pg("UPDATE users SET status=%s, updated_at=CURRENT_TIMESTAMP WHERE id = %s",
            (original, JORDAN_USER))


def test_admin_role_assignment_persists(client):
    tok = _login(client, "admin@amap.com")
    try:
        res = client.post(f"/api/v1/admin/users/{JORDAN_USER}/roles",
                          json={"role_name": "supervisor"}, headers=_auth(tok))
        assert res.status_code == 200, res.text
        row = _pg(
            "SELECT r.name FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
            "WHERE ur.user_id = %s AND r.name = 'supervisor'",
            (JORDAN_USER,),
        )
        assert row, "role assignment must persist"
        audit = _pg(
            "SELECT 1 FROM audit_events WHERE resource_id = %s "
            "AND event_type = 'user.role_assigned'",
            (JORDAN_USER,),
        )
        assert audit
        # revoke -> gone
        res = client.delete(f"/api/v1/admin/users/{JORDAN_USER}/roles/supervisor",
                            headers=_auth(tok))
        assert res.status_code == 200, res.text
        row = _pg(
            "SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
            "WHERE ur.user_id = %s AND r.name = 'supervisor'",
            (JORDAN_USER,),
        )
        assert not row, "revocation must delete the row"
    finally:
        _pg(
            "DELETE FROM user_roles WHERE user_id = %s AND role_id = "
            "(SELECT id FROM roles WHERE name = 'supervisor')",
            (JORDAN_USER,),
        )


# ---------------------------------------------------------------------------
# Assistance + emergencies (were fabricated / hardcoded empty)
# ---------------------------------------------------------------------------

def test_assistance_overview_and_emergencies_from_database(client):
    tok = _login(client, "admin@amap.com")
    # start from a clean slate for this org's overview
    req_id = str(uuid4())
    _pg(
        "INSERT INTO assistance_requests (id, organization_id, worker_profile_id, "
        "status, priority, reason) VALUES (%s, %s, %s, 'open', 'urgent', "
        "'Emergency stop: line 2 jam')",
        (req_id, ORG, ALEX),
    )
    try:
        res = client.get("/api/v1/organizations/manage/assistance", headers=_auth(tok))
        assert res.status_code == 200, res.text
        items = res.json()
        mine = [i for i in items if i["id"] == req_id]
        assert len(mine) == 1, "real assistance row must be listed"
        assert mine[0]["worker_name"] == "Alex Morgan (Worker)"  # resolved, not fabricated
        assert mine[0]["priority"] == "urgent"
        assert mine[0]["is_emergency"] is True
        # every listed id exists in the table (no fabricated Samira Chen rows)
        db_ids = {str(r[0]) for r in _pg(
            "SELECT id FROM assistance_requests WHERE organization_id = %s", (ORG,))}
        assert {i["id"] for i in items} <= db_ids
        assert all(i["worker_name"] != "Samira Chen" or str(i["id"]) in db_ids
                   for i in items)

        res = client.get("/api/v1/organizations/manage/emergencies", headers=_auth(tok))
        assert res.status_code == 200, res.text
        emerg_ids = {i["id"] for i in res.json()}
        assert req_id in emerg_ids, "active urgent request must surface as emergency"

        # resolve -> no longer an active emergency
        _pg("UPDATE assistance_requests SET status='resolved', "
            "resolved_at=CURRENT_TIMESTAMP WHERE id=%s", (req_id,))
        res = client.get("/api/v1/organizations/manage/emergencies", headers=_auth(tok))
        assert req_id not in {i["id"] for i in res.json()}
        res = client.get("/api/v1/organizations/manage/assistance", headers=_auth(tok))
        resolved = [i for i in res.json() if i["id"] == req_id][0]
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
    finally:
        _pg("DELETE FROM assistance_requests WHERE id = %s", (req_id,))


# ---------------------------------------------------------------------------
# Analytics + dashboard (were hardcoded constants)
# ---------------------------------------------------------------------------

def test_analytics_values_match_sql_truth(client):
    tok = _login(client, "admin@amap.com")
    res = client.get("/api/v1/organizations/manage/analytics", headers=_auth(tok))
    assert res.status_code == 200, res.text
    a = res.json()

    completed, in_prog, durations = _pg(
        """
        SELECT COUNT(*) FILTER (WHERE a.status = 'completed'),
               COUNT(*) FILTER (WHERE a.status IN ('in_progress', 'assigned', 'paused')),
               COALESCE(
                   array_agg(
                       (EXTRACT(EPOCH FROM (a.completed_at - a.started_at)) / 60.0)
                   ) FILTER (WHERE a.status = 'completed'
                               AND a.started_at IS NOT NULL
                               AND a.completed_at IS NOT NULL),
                   ARRAY[]::float8[]
               )
        FROM worker_task_assignments a
        JOIN tasks t ON t.id = a.task_id
        WHERE t.organization_id = %s
        """,
        (ORG,),
    )[0]
    assigned = _pg(
        "SELECT COUNT(*) FROM worker_task_assignments a JOIN tasks t ON t.id = a.task_id "
        "WHERE t.organization_id = %s",
        (ORG,),
    )[0][0]
    assist_total, assist_resolved = _pg(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) "
        "FROM assistance_requests WHERE organization_id = %s",
        (ORG,),
    )[0]
    emerg = _pg(
        "SELECT COUNT(*) FROM assistance_requests WHERE organization_id = %s "
        "AND (priority = 'urgent' OR LOWER(COALESCE(reason,'')) LIKE '%%emergency%%') "
        "AND status IN ('open','acknowledged','in_progress')",
        (ORG,),
    )[0][0]

    assert a["tasks_completed_count"] == completed
    assert a["tasks_in_progress_count"] == in_prog
    assert a["total_assistance_requests"] == assist_total
    assert a["emergency_stops_count"] == emerg
    expected_rate = round((completed / assigned) * 100.0, 1) if assigned else 0.0
    assert abs(a["workflow_completion_rate"] - expected_rate) < 0.11
    if durations:
        expected_dur = round(sum(durations) / len(durations), 1)
        assert abs(a["average_task_duration_minutes"] - expected_dur) < 0.11
    else:
        assert a["average_task_duration_minutes"] == 0.0
    if assist_resolved:
        assert a["average_resolution_time_minutes"] >= 0.0
    else:
        assert a["average_resolution_time_minutes"] == 0.0
    # the old hardcoded constants must not appear unless they equal real truth
    assert not (completed == 19 and in_prog == 3 and a["total_assistance_requests"] == 6
                and a["workflow_completion_rate"] == 94.5
                and a["average_task_duration_minutes"] == 8.2), \
        "analytics still look like the hardcoded constants"


def test_dashboard_kpis_match_sql_truth(client):
    tok = _login(client, "admin@amap.com")
    res = client.get("/api/v1/organizations/manage/dashboard", headers=_auth(tok))
    assert res.status_code == 200, res.text
    d = res.json()

    total, completed, in_prog, assigned = _pg(
        """
        SELECT
            (SELECT COUNT(*) FROM users u JOIN worker_profiles wp ON wp.user_id = u.id
              WHERE u.organization_id = %s),
            (SELECT COUNT(*) FROM worker_task_assignments a
               JOIN tasks t ON t.id = a.task_id
              WHERE t.organization_id = %s AND a.status = 'completed'),
            (SELECT COUNT(*) FROM worker_task_assignments a
               JOIN tasks t ON t.id = a.task_id
              WHERE t.organization_id = %s AND a.status = 'in_progress'),
            (SELECT COUNT(*) FROM worker_task_assignments a
               JOIN tasks t ON t.id = a.task_id
              WHERE t.organization_id = %s AND a.status = 'assigned')
        """,
        (ORG, ORG, ORG, ORG),
    )[0]
    assert d["total_workers_count"] == total
    assert d["completed_tasks_count"] == completed
    assert d["active_tasks_count"] == in_prog
    assert d["pending_tasks_count"] == assigned
    assert d["organization_name"] == "Acme Motors — Assembly Plant 1"
    assert d["supervisors_count"] == _pg(
        "SELECT COUNT(*) FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
        "JOIN users u ON u.id = ur.user_id "
        "WHERE r.name = 'supervisor' AND u.organization_id = %s",
        (ORG,),
    )[0][0]
