"""Phase 6 workflow CRUD integration tests (real PostgreSQL, real API path).

Covers:
- List: workflows and steps are read from PostgreSQL — the previously
  hardcoded templates ("High-Voltage Isolation Check", "Planetary
  Gearbox Assembly") must not appear unless they are real rows.
- Create: workflow + every step persisted (Department/version/duration
  metadata and per-step safety fields included); duplicate -> 409.
- Update: rename/status/steps actually persist (was audit-only) and the
  version bumps; executed steps cannot be silently deleted (409).
- Tenant isolation: unknown/cross-tenant workflow -> 404, no mutation.
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
SEED_WORKFLOW_ID = "e0000000-0000-0000-0000-000000000001"
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


def _cleanup_workflow(workflow_id):
    """Remove a workflow and everything referencing it, in FK order."""
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM workflow_step_executions e
                USING workflow_assignments a
                WHERE e.workflow_assignment_id = a.id
                  AND a.workflow_id = %s
                """,
                (workflow_id,),
            )
            cur.execute(
                "DELETE FROM workflow_assignments WHERE workflow_id = %s",
                (workflow_id,),
            )
            cur.execute(
                "DELETE FROM workflow_step_responsibilities "
                "WHERE workflow_step_id IN (SELECT id FROM workflow_steps WHERE workflow_id = %s)",
                (workflow_id,),
            )
            cur.execute("DELETE FROM workflow_steps WHERE workflow_id = %s", (workflow_id,))
            cur.execute("DELETE FROM workflows WHERE id = %s", (workflow_id,))
            cur.execute(
                "DELETE FROM audit_events WHERE resource_id = %s AND event_type "
                "IN ('workflow.created', 'workflow.updated')",
                (workflow_id,),
            )
        conn.commit()


def test_workflow_list_returns_database_rows(client, admin_token):
    """GET /workflows must reflect PostgreSQL, not the old hardcoded trio."""
    res = client.get(
        "/api/v1/organizations/manage/workflows", headers=_auth(admin_token)
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    items = res.json()
    assert len(items) >= 1

    db_rows = _pg(
        "SELECT id, name, status, version FROM workflows WHERE organization_id = %s",
        (ORG_A,),
    )
    db_by_id = {str(r[0]): r for r in db_rows}
    names = set()
    for item in items:
        assert item["id"] in db_by_id, f"workflow {item['id']} not in PostgreSQL"
        row = db_by_id[item["id"]]
        assert item["name"] == row[1]
        assert item["status"] == row[2]
        assert item["version"] == row[3]
        # steps come from workflow_steps table
        step_rows = _pg(
            "SELECT step_order, name, is_safety_critical FROM workflow_steps "
            "WHERE workflow_id = %s ORDER BY step_order",
            (item["id"],),
        )
        assert item["step_count"] == len(step_rows)
        assert len(item["steps"]) == len(step_rows)
        for api_step, db_step in zip(item["steps"], step_rows):
            assert api_step["step_number"] == db_step[0]
            assert api_step["title"] == db_step[1]
            assert api_step["is_safety_critical"] == db_step[2]
        names.add(item["name"])

    # The two fabricated templates from the old hardcoded list must be absent
    # unless they exist as real rows (fresh DBs never contain them).
    for fabricated in ("High-Voltage Isolation Check", "Planetary Gearbox Assembly"):
        exists = _pg(
            "SELECT 1 FROM workflows WHERE organization_id = %s AND name = %s",
            (ORG_A, fabricated),
        )
        if not exists:
            assert fabricated not in names


def test_create_workflow_persists_rows_and_steps(client, admin_token):
    """POST /workflows writes the workflow and every step to PostgreSQL."""
    name = f"Phase6 Create {uuid4().hex[:6]}"
    payload = {
        "name": name,
        "description": "Phase 6 persisted template",
        "steps": [
            {
                "title": "Seat the bearing",
                "instruction": "Press bearing into housing with 12 kN force.",
                "is_safety_critical": True,
                "expected_duration_seconds": 90,
                "required_intent": "CONFIRM",
            },
            {
                "title": "Torque cover bolts",
                "instruction": "Star pattern to 8.5 Nm.",
                "is_safety_critical": False,
                "expected_duration_seconds": 150,
            },
        ],
        "estimated_duration_minutes": 7.5,
    }
    res = client.post(
        "/api/v1/organizations/manage/workflows",
        json=payload,
        headers=_auth(admin_token),
    )
    assert res.status_code == status.HTTP_201_CREATED, res.text
    body = res.json()
    wf_id = body["id"]

    try:
        wf_rows = _pg(
            "SELECT name, description, status, version, estimated_duration_minutes "
            "FROM workflows WHERE id = %s",
            (wf_id,),
        )
        assert len(wf_rows) == 1
        assert wf_rows[0][0] == name
        assert wf_rows[0][2] == "active"
        assert wf_rows[0][3] == 1
        assert float(wf_rows[0][4]) == 7.5

        step_rows = _pg(
            "SELECT step_order, name, description, is_safety_critical, "
            "expected_duration_seconds, required_intent "
            "FROM workflow_steps WHERE workflow_id = %s ORDER BY step_order",
            (wf_id,),
        )
        assert len(step_rows) == 2
        assert step_rows[0][0] == 1 and step_rows[0][1] == "Seat the bearing"
        assert step_rows[0][3] is True
        assert step_rows[0][4] == 90
        assert step_rows[0][5] == "CONFIRM"
        assert step_rows[1][4] == 150
        assert step_rows[1][5] is None

        # response mirrors the database
        assert body["step_count"] == 2
        assert body["steps"][0]["title"] == "Seat the bearing"
        assert body["steps"][0]["is_safety_critical"] is True
        assert body["steps"][0]["required_intent"] == "CONFIRM"

        audit = _pg(
            "SELECT 1 FROM audit_events WHERE resource_id = %s AND event_type = 'workflow.created'",
            (wf_id,),
        )
        assert audit
    finally:
        _cleanup_workflow(wf_id)


def test_create_duplicate_workflow_returns_409(client, admin_token):
    """Duplicate workflow names are a conflict (409), not a silent success."""
    name = f"Phase6 Dup {uuid4().hex[:6]}"
    payload = {"name": name, "steps": [{"title": "Only step"}]}
    first = client.post(
        "/api/v1/organizations/manage/workflows",
        json=payload,
        headers=_auth(admin_token),
    )
    assert first.status_code == status.HTTP_201_CREATED, first.text
    wf_id = first.json()["id"]
    try:
        second = client.post(
            "/api/v1/organizations/manage/workflows",
            json=payload,
            headers=_auth(admin_token),
        )
        assert second.status_code == status.HTTP_409_CONFLICT, second.text
        count = _pg(
            "SELECT COUNT(*) FROM workflows WHERE organization_id = %s AND name = %s",
            (ORG_A, name),
        )
        assert count[0][0] == 1
    finally:
        _cleanup_workflow(wf_id)


def test_update_workflow_persists_rename_status_and_version(client, admin_token):
    """PUT /workflows persists rename/status (was audit-only) and bumps version."""
    name = f"Phase6 Update {uuid4().hex[:6]}"
    new_name = name + " v2"
    created = client.post(
        "/api/v1/organizations/manage/workflows",
        json={"name": name, "steps": [{"title": "Step one"}]},
        headers=_auth(admin_token),
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    wf_id = created.json()["id"]
    try:
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{wf_id}",
            json={"name": new_name, "status": "archived"},
            headers=_auth(admin_token),
        )
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert body["name"] == new_name
        assert body["status"] == "archived"
        assert body["version"] == 2  # version bumped on update

        row = _pg(
            "SELECT name, status, version FROM workflows WHERE id = %s", (wf_id,)
        )
        assert row[0][0] == new_name
        assert row[0][1] == "archived"
        assert row[0][2] == 2

        audit = _pg(
            "SELECT 1 FROM audit_events WHERE resource_id = %s AND event_type = 'workflow.updated'",
            (wf_id,),
        )
        assert audit
    finally:
        _cleanup_workflow(wf_id)


def test_update_workflow_rename_conflict_409(client, admin_token):
    """Renaming onto an existing workflow name must 409 with no mutation."""
    suffix = uuid4().hex[:6]
    a_name = f"Phase6 A {suffix}"
    b_name = f"Phase6 B {suffix}"
    a = client.post(
        "/api/v1/organizations/manage/workflows",
        json={"name": a_name, "steps": [{"title": "S1"}]},
        headers=_auth(admin_token),
    )
    b = client.post(
        "/api/v1/organizations/manage/workflows",
        json={"name": b_name, "steps": [{"title": "S1"}]},
        headers=_auth(admin_token),
    )
    assert a.status_code == 201 and b.status_code == 201
    a_id, b_id = a.json()["id"], b.json()["id"]
    try:
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{a_id}",
            json={"name": b_name},
            headers=_auth(admin_token),
        )
        assert res.status_code == status.HTTP_409_CONFLICT, res.text
        row = _pg("SELECT name FROM workflows WHERE id = %s", (a_id,))
        assert row[0][0] == a_name  # unchanged
    finally:
        _cleanup_workflow(a_id)
        _cleanup_workflow(b_id)


def test_update_workflow_steps_persists_exact_step_set(client, admin_token):
    """PUT with steps rewrites workflow_steps to exactly the payload."""
    name = f"Phase6 Steps {uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/organizations/manage/workflows",
        json={
            "name": name,
            "steps": [
                {"title": "Old one"},
                {"title": "Old two"},
                {"title": "Old three"},
            ],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text
    wf_id = created.json()["id"]
    try:
        new_steps = [
            {
                "title": "New A",
                "instruction": "First",
                "is_safety_critical": True,
                "expected_duration_seconds": 45,
                "required_intent": "NEXT_STEP",
            },
            {
                "title": "New B",
                "instruction": "Second",
                "is_safety_critical": False,
                "expected_duration_seconds": 60,
            },
        ]
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{wf_id}",
            json={"steps": new_steps},
            headers=_auth(admin_token),
        )
        assert res.status_code == 200, res.text
        assert res.json()["step_count"] == 2

        rows = _pg(
            "SELECT step_order, name, description, is_safety_critical, "
            "expected_duration_seconds, required_intent "
            "FROM workflow_steps WHERE workflow_id = %s ORDER BY step_order",
            (wf_id,),
        )
        assert len(rows) == 2
        assert [r[0] for r in rows] == [1, 2]
        assert rows[0][1] == "New A" and rows[0][3] is True
        assert rows[0][4] == 45 and rows[0][5] == "NEXT_STEP"
        assert rows[1][1] == "New B" and rows[1][5] is None
        # old third step removed
        gone = _pg(
            "SELECT 1 FROM workflow_steps WHERE workflow_id = %s AND name = 'Old three'",
            (wf_id,),
        )
        assert not gone
    finally:
        _cleanup_workflow(wf_id)


def test_update_unknown_or_cross_tenant_workflow_404(client, admin_token):
    """Unknown and cross-tenant workflow ids 404 without touching data."""
    res = client.put(
        f"/api/v1/organizations/manage/workflows/{uuid4()}",
        json={"name": "Ghost"},
        headers=_auth(admin_token),
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND, res.text

    # cross-tenant: real workflow owned by a different organization
    other_org = str(uuid4())
    cross_id = str(uuid4())
    _pg(
        "INSERT INTO organizations (id, name, status) VALUES (%s, %s, 'active')",
        (other_org, f"Phase6 other org {uuid4().hex[:6]}"),
    )
    _pg(
        "INSERT INTO workflows (id, organization_id, name, status) VALUES (%s, %s, %s, 'active')",
        (cross_id, other_org, f"Phase6 OrgB {uuid4().hex[:6]}"),
    )
    try:
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{cross_id}",
            json={"name": "Hijacked"},
            headers=_auth(admin_token),
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND, res.text
        row = _pg("SELECT name FROM workflows WHERE id = %s", (cross_id,))
        assert row[0][0] != "Hijacked"
    finally:
        _cleanup_workflow(cross_id)
        _pg("DELETE FROM organizations WHERE id = %s", (other_org,))


def test_update_workflow_invalid_status_400(client, admin_token):
    """Invalid status values surface as a domain 400, not a silent accept."""
    created = client.post(
        "/api/v1/organizations/manage/workflows",
        json={"name": f"Phase6 Status {uuid4().hex[:6]}", "steps": [{"title": "S"}]},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text
    wf_id = created.json()["id"]
    try:
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{wf_id}",
            json={"status": "bogus_status"},
            headers=_auth(admin_token),
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text
        row = _pg("SELECT status FROM workflows WHERE id = %s", (wf_id,))
        assert row[0][0] == "active"  # unchanged
    finally:
        _cleanup_workflow(wf_id)


def test_step_without_title_rejected_400(client, admin_token):
    """A step payload entry without a title is a 400, not a blank step."""
    res = client.post(
        "/api/v1/organizations/manage/workflows",
        json={
            "name": f"Phase6 Empty {uuid4().hex[:6]}",
            "steps": [{"instruction": "no title here"}],
        },
        headers=_auth(admin_token),
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text


def test_executed_step_cannot_be_removed(client, admin_token):
    """Steps with workflow_step_executions history cannot be deleted (409)."""
    name = f"Phase6 Exec {uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/organizations/manage/workflows",
        json={
            "name": name,
            "steps": [{"title": "Executed step"}, {"title": "Removable step"}],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text
    wf_id = created.json()["id"]

    profile = _pg(
        "SELECT wp.id FROM worker_profiles wp JOIN users u ON u.id = wp.user_id "
        "WHERE u.organization_id = %s LIMIT 1",
        (ORG_A,),
    )
    assert profile, "expected a seeded worker profile"
    try:
        # create assignment + execution for step 2 (raw SQL fixture)
        assignment_id = str(uuid4())
        _pg(
            "INSERT INTO workflow_assignments (id, workflow_id, worker_profile_id, status) "
            "VALUES (%s, %s, %s, 'assigned')",
            (assignment_id, wf_id, profile[0][0]),
        )
        step2 = _pg(
            "SELECT id FROM workflow_steps WHERE workflow_id = %s AND step_order = 2",
            (wf_id,),
        )
        _pg(
            "INSERT INTO workflow_step_executions "
            "(id, workflow_assignment_id, workflow_step_id, status) VALUES (%s, %s, %s, 'pending')",
            (str(uuid4()), assignment_id, step2[0][0]),
        )

        # shrink to one step -> must 409, data unchanged
        res = client.put(
            f"/api/v1/organizations/manage/workflows/{wf_id}",
            json={"steps": [{"title": "Only kept"}]},
            headers=_auth(admin_token),
        )
        assert res.status_code == status.HTTP_409_CONFLICT, res.text
        rows = _pg(
            "SELECT name FROM workflow_steps WHERE workflow_id = %s ORDER BY step_order",
            (wf_id,),
        )
        assert len(rows) == 2  # unchanged
        assert rows[1][0] == "Removable step"
    finally:
        _cleanup_workflow(wf_id)


def test_create_workflow_with_department_persists_ownership(client, admin_token):
    """department_id on create persists and resolves to a real name."""
    dept = _pg(
        "SELECT id, name FROM departments WHERE organization_id = %s LIMIT 1",
        (ORG_A,),
    )
    assert dept, "expected a seeded department"
    name = f"Phase6 Dept {uuid4().hex[:6]}"
    res = client.post(
        "/api/v1/organizations/manage/workflows",
        json={
            "name": name,
            "department_id": str(dept[0][0]),
            "steps": [{"title": "S1"}],
        },
        headers=_auth(admin_token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    wf_id = body["id"]
    try:
        row = _pg("SELECT department_id FROM workflows WHERE id = %s", (wf_id,))
        assert str(row[0][0]) == str(dept[0][0])
        assert body["department_name"] == dept[0][1]
    finally:
        _cleanup_workflow(wf_id)


def test_seed_workflow_has_real_steps(client, admin_token):
    """The seeded workflow returns its three real PostgreSQL steps."""
    res = client.get(
        "/api/v1/organizations/manage/workflows", headers=_auth(admin_token)
    )
    assert res.status_code == 200, res.text
    seeded = [i for i in res.json() if i["id"] == SEED_WORKFLOW_ID]
    if not seeded:
        pytest.skip("seed workflow not present in this database")
    item = seeded[0]
    rows = _pg(
        "SELECT step_order, name FROM workflow_steps WHERE workflow_id = %s "
        "ORDER BY step_order",
        (SEED_WORKFLOW_ID,),
    )
    assert item["step_count"] == len(rows) == 3
    assert [s["step_number"] for s in item["steps"]] == [1, 2, 3]
    assert [s["title"] for s in item["steps"]] == [r[1] for r in rows]
