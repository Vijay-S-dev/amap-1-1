"""Phase 7 assignment + result lifecycle integration tests (real PostgreSQL).

Covers the full chain the acceptance standard requires:
supervisor assigns -> worker sees -> start -> ordered step execution ->
complete -> result persisted in task_results -> supervisor reads result,
plus RBAC (worker denied supervisor endpoints, non-owner denied results),
cross-tenant denial, invalid state transitions, reassignment, honest
supervisor telemetry (progress/step/health from real rows, never
hardcoded), and refresh/re-login persistence.

Every fixture row (workflow, steps, task, link) is created and cleaned
up per test so the suite is hermetic against the seeded database.
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"  # worker profile (alex.worker)
JORDAN = "d0000000-0000-0000-0000-000000000002"  # worker profile (jordan.worker)
DEFAULT_PASSWORD = "SecurePassword123!"
# verified PBKDF2 hash from Phase 2 (SecurePassword123!)
VERIFIED_HASH = (
    "pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$"
    "10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9"
)

STEP_NAMES = ["Phase7 Seating", "Phase7 Torquing", "Phase7 QA signoff"]


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _login(client, email, org_id=ORG):
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": org_id, "email": email, "password": DEFAULT_PASSWORD},
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


@pytest.fixture()
def phase7_task():
    """Dedicated workflow (3 named steps) + task + link in the seed org."""
    wf_id, task_id = str(uuid4()), str(uuid4())
    step_ids = [str(uuid4()) for _ in range(3)]
    _pg(
        "INSERT INTO workflows (id, organization_id, name, description, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (wf_id, ORG, f"Phase7 Workflow {uuid4().hex[:6]}", "Phase 7 fixture"),
    )
    for i, (sid, name) in enumerate(zip(step_ids, STEP_NAMES), start=1):
        _pg(
            "INSERT INTO workflow_steps (id, workflow_id, step_order, name, description, "
            "is_safety_critical, expected_duration_seconds, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')",
            (sid, wf_id, i, name, f"Do {name}.", i == 2, 60 * i),
        )
    _pg(
        "INSERT INTO tasks (id, organization_id, name, description, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (task_id, ORG, f"Phase7 Task {uuid4().hex[:6]}", "Phase 7 fixture task"),
    )
    _pg("INSERT INTO task_workflows (task_id, workflow_id) VALUES (%s, %s)", (task_id, wf_id))
    yield {"workflow_id": wf_id, "task_id": task_id, "step_ids": step_ids}
    # cleanup in FK order
    _pg(
        "DELETE FROM workflow_step_executions WHERE workflow_assignment_id IN "
        "(SELECT id FROM workflow_assignments WHERE workflow_id = %s)",
        (wf_id,),
    )
    _pg("DELETE FROM workflow_assignments WHERE workflow_id = %s", (wf_id,))
    _pg("DELETE FROM task_workflows WHERE task_id = %s", (task_id,))
    _pg(
        "DELETE FROM task_results WHERE worker_task_assignment_id IN "
        "(SELECT id FROM worker_task_assignments WHERE task_id = %s)",
        (task_id,),
    )
    _pg("DELETE FROM worker_task_assignments WHERE task_id = %s", (task_id,))
    _pg(
        "DELETE FROM audit_events WHERE resource_id IN "
        "(SELECT id FROM worker_task_assignments WHERE task_id = %s) "
        "OR resource_id = %s",
        (task_id, task_id),
    )
    _pg("DELETE FROM tasks WHERE id = %s", (task_id,))
    _pg("DELETE FROM workflow_step_responsibilities WHERE workflow_step_id IN "
        "(SELECT id FROM workflow_steps WHERE workflow_id = %s)", (wf_id,))
    _pg("DELETE FROM workflow_steps WHERE workflow_id = %s", (wf_id,))
    _pg("DELETE FROM workflows WHERE id = %s", (wf_id,))


def _assign(client, sup_token, task_id, worker_profile_id):
    return client.post(
        "/api/v1/supervisor/tasks/assign",
        json={"task_id": task_id, "worker_profile_id": worker_profile_id},
        headers=_auth(sup_token),
    )


# ---------------------------------------------------------------------------
# Assignment creation (supervisor) + worker visibility + start
# ---------------------------------------------------------------------------

def test_supervisor_assign_persists_assignment_row(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    res = _assign(client, sup, phase7_task["task_id"], ALEX)
    assert res.status_code == status.HTTP_201_CREATED, res.text
    assignment_id = res.json()["assignment"]["id"]

    row = _pg(
        "SELECT status, assigned_at FROM worker_task_assignments WHERE id = %s",
        (assignment_id,),
    )
    assert row, "assignment row must exist in PostgreSQL"
    assert row[0][0] == "assigned"
    assert row[0][1] is not None, "assigned_at must be persisted"

    audit = _pg(
        "SELECT 1 FROM audit_events WHERE resource_id = %s "
        "AND event_type = 'supervisor_task_assigned'",
        (assignment_id,),
    )
    assert audit, "assignment must be audited"


def test_worker_sees_assignment_and_start_persists(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    assigned = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]
    aid = assigned["id"]

    # Worker sees it (fresh read)
    alex = _login(client, "alex.worker@amap.com")
    lst = client.get("/api/v1/tasks/assigned", headers=_auth(alex))
    assert lst.status_code == 200, lst.text
    assert aid in [a["id"] for a in lst.json()]

    # Start -> persisted state transition
    res = client.post(f"/api/v1/tasks/assignments/{aid}/start", headers=_auth(alex))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "in_progress"

    row = _pg(
        "SELECT status, started_at FROM worker_task_assignments WHERE id = %s", (aid,)
    )
    assert row[0][0] == "in_progress"
    assert row[0][1] is not None, "started_at must persist"

    # refresh persistence: new GET still shows in_progress
    lst2 = client.get("/api/v1/tasks/assigned", headers=_auth(alex))
    item = next(a for a in lst2.json() if a["id"] == aid)
    assert item["status"] == "in_progress"

    # re-login persistence: brand-new token, same state
    alex2 = _login(client, "alex.worker@amap.com")
    lst3 = client.get("/api/v1/tasks/assigned", headers=_auth(alex2))
    item = next(a for a in lst3.json() if a["id"] == aid)
    assert item["status"] == "in_progress"

    # linked workflow assignment created in_progress
    wf_rows = _pg(
        "SELECT status FROM workflow_assignments WHERE workflow_id = %s "
        "AND worker_profile_id = %s",
        (phase7_task["workflow_id"], ALEX),
    )
    assert wf_rows and wf_rows[0][0] == "in_progress"


def test_other_worker_cannot_touch_assignment(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
    jordan = _login(client, "jordan.worker@amap.com")

    res = client.post(f"/api/v1/tasks/assignments/{aid}/start", headers=_auth(jordan))
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text
    res = client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed"},
        headers=_auth(jordan),
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text
    row = _pg("SELECT status FROM worker_task_assignments WHERE id = %s", (aid,))
    assert row[0][0] == "assigned"  # untouched


def test_worker_cannot_use_supervisor_assignment_endpoint(client, phase7_task):
    alex = _login(client, "alex.worker@amap.com")
    res = _assign(client, alex, phase7_task["task_id"], JORDAN)
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text
    count = _pg(
        "SELECT COUNT(*) FROM worker_task_assignments WHERE task_id = %s",
        (phase7_task["task_id"],),
    )
    assert count[0][0] == 0


# ---------------------------------------------------------------------------
# Step execution: order enforcement + persistence
# ---------------------------------------------------------------------------

def _start(client, token, aid):
    res = client.post(f"/api/v1/tasks/assignments/{aid}/start", headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()


def test_step_order_enforced_and_execution_persists(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    alex = _login(client, "alex.worker@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
    _start(client, alex, aid)

    wf_assign = _pg(
        "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (phase7_task["workflow_id"], ALEX),
    )[0][0]
    s1, s2, s3 = phase7_task["step_ids"]

    # step 2 before step 1 -> 409 order violation, nothing written
    res = client.post(
        f"/api/v1/tasks/workflows/assignments/{wf_assign}/steps/{s2}/execute",
        json={"status": "completed"},
        headers=_auth(alex),
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text
    rows = _pg(
        "SELECT COUNT(*) FROM workflow_step_executions WHERE workflow_assignment_id = %s",
        (wf_assign,),
    )
    assert rows[0][0] == 0

    # valid: step 1 completed -> row persisted with timestamps
    res = client.post(
        f"/api/v1/tasks/workflows/assignments/{wf_assign}/steps/{s1}/execute",
        json={"status": "completed", "execution_data": {"torque_nm": 9.2}},
        headers=_auth(alex),
    )
    assert res.status_code == status.HTTP_201_CREATED, res.text
    row = _pg(
        "SELECT status, started_at, completed_at, notes "
        "FROM workflow_step_executions WHERE workflow_assignment_id = %s "
        "AND workflow_step_id = %s",
        (wf_assign, s1),
    )
    assert row[0][0] == "completed"
    assert row[0][1] is not None and row[0][2] is not None
    assert "torque_nm" in row[0][3]

    # step 2 now allowed
    res = client.post(
        f"/api/v1/tasks/workflows/assignments/{wf_assign}/steps/{s2}/execute",
        json={"status": "completed"},
        headers=_auth(alex),
    )
    assert res.status_code == status.HTTP_201_CREATED, res.text


def test_complete_requires_all_steps(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    jordan = _login(client, "jordan.worker@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], JORDAN).json()["assignment"]["id"]
    _start(client, jordan, aid)

    res = client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed"},
        headers=_auth(jordan),
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text
    row = _pg("SELECT status FROM worker_task_assignments WHERE id = %s", (aid,))
    assert row[0][0] == "in_progress"  # not silently completed
    results = _pg(
        "SELECT COUNT(*) FROM task_results WHERE worker_task_assignment_id = %s", (aid,)
    )
    assert results[0][0] == 0  # no fake result row


def _complete_all_steps(client, token, wf_assign_id, step_ids):
    for sid in step_ids:
        res = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assign_id}/steps/{sid}/execute",
            json={"status": "completed"},
            headers=_auth(token),
        )
        assert res.status_code == status.HTTP_201_CREATED, res.text


def test_complete_persists_result_and_timestamps(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    alex = _login(client, "alex.worker@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
    _start(client, alex, aid)
    wf_assign = _pg(
        "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (phase7_task["workflow_id"], ALEX),
    )[0][0]
    _complete_all_steps(client, alex, wf_assign, phase7_task["step_ids"])

    res = client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed", "result_data": {"defects": 0}, "notes": "all good"},
        headers=_auth(alex),
    )
    assert res.status_code == 200, res.text

    row = _pg(
        "SELECT status, started_at, completed_at FROM worker_task_assignments WHERE id = %s",
        (aid,),
    )
    assert row[0][0] == "completed"
    assert row[0][1] is not None and row[0][2] is not None

    result = _pg(
        "SELECT outcome, result_data, notes FROM task_results "
        "WHERE worker_task_assignment_id = %s",
        (aid,),
    )
    assert len(result) == 1, "exactly one authoritative result row"
    outcome, result_data, notes = result[0]
    assert outcome == "completed"
    assert notes == "all good"
    # server-computed truth present and consistent
    assert result_data["completed_steps"] == 3
    assert result_data["total_steps"] == 3
    assert result_data["outcome"] == "completed"
    assert "duration_seconds" in result_data
    assert result_data.get("defects") == 0

    # workflow assignment synchronized
    wf_row = _pg(
        "SELECT status FROM workflow_assignments WHERE id = %s", (wf_assign,)
    )
    assert wf_row[0][0] == "completed"

    # refresh persistence: fresh GET of result
    fresh = _login(client, "alex.worker@amap.com")
    res2 = client.get(f"/api/v1/tasks/assignments/{aid}/result", headers=_auth(fresh))
    assert res2.status_code == 200, res2.text
    assert res2.json()["outcome"] == "completed"


def test_result_visibility_rbac_and_tenancy(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    alex = _login(client, "alex.worker@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
    _start(client, alex, aid)
    wf_assign = _pg(
        "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (phase7_task["workflow_id"], ALEX),
    )[0][0]
    _complete_all_steps(client, alex, wf_assign, phase7_task["step_ids"])
    client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed"},
        headers=_auth(alex),
    )

    # owner worker: 200
    res = client.get(f"/api/v1/tasks/assignments/{aid}/result", headers=_auth(alex))
    assert res.status_code == 200, res.text

    # supervisor: 200
    res = client.get(f"/api/v1/tasks/assignments/{aid}/result", headers=_auth(sup))
    assert res.status_code == 200, res.text

    # other worker in same org: 403
    jordan = _login(client, "jordan.worker@amap.com")
    res = client.get(f"/api/v1/tasks/assignments/{aid}/result", headers=_auth(jordan))
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text

    # user from ANOTHER organization: 403 (created in PostgreSQL for real)
    other_org = str(uuid4())
    other_user = str(uuid4())
    outsider_email = f"outsider-{uuid4().hex[:8]}@example.com"
    _pg(
        "INSERT INTO organizations (id, name, status) VALUES (%s, %s, 'active')",
        (other_org, f"Phase7 org {uuid4().hex[:6]}"),
    )
    _pg(
        "INSERT INTO users (id, organization_id, email, full_name, password_hash, status) "
        "VALUES (%s, %s, %s, 'Outsider', %s, 'active')",
        (other_user, other_org, outsider_email, VERIFIED_HASH),
    )
    try:
        outsider = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": other_org,
                "email": outsider_email,
                "password": DEFAULT_PASSWORD,
            },
        )
        assert outsider.status_code == 200, outsider.text
        otok = outsider.json()["access_token"]
        res = client.get(f"/api/v1/tasks/assignments/{aid}/result", headers=_auth(otok))
        assert res.status_code == status.HTTP_403_FORBIDDEN, res.text
    finally:
        _pg("DELETE FROM users WHERE id = %s", (other_user,))
        _pg("DELETE FROM organizations WHERE id = %s", (other_org,))


def test_task_details_step_titles_are_real(client, phase7_task):
    """GET /tasks/{id} must expose real step names, not fabricated 'Step N'."""
    sup = _login(client, "supervisor@amap.com")
    res = client.get(f"/api/v1/tasks/{phase7_task['task_id']}", headers=_auth(sup))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_steps"] == 3
    titles = [s["title"] for s in body["steps"]]
    assert titles == STEP_NAMES, f"titles must come from workflow_steps, got {titles}"
    instructions = [s["instructionText"] for s in body["steps"]]
    assert all(i.startswith("Do ") for i in instructions)


# ---------------------------------------------------------------------------
# Invalid transitions + reassignment
# ---------------------------------------------------------------------------

def test_invalid_state_transitions_rejected(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    alex = _login(client, "alex.worker@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
    _start(client, alex, aid)
    wf_assign = _pg(
        "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (phase7_task["workflow_id"], ALEX),
    )[0][0]
    _complete_all_steps(client, alex, wf_assign, phase7_task["step_ids"])
    client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed"},
        headers=_auth(alex),
    )

    # start completed -> 409
    res = client.post(f"/api/v1/tasks/assignments/{aid}/start", headers=_auth(alex))
    assert res.status_code == status.HTTP_409_CONFLICT, res.text
    # complete again -> 409
    res = client.post(
        f"/api/v1/tasks/assignments/{aid}/complete",
        json={"outcome": "completed"},
        headers=_auth(alex),
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text
    # record step on completed workflow assignment -> 409
    res = client.post(
        f"/api/v1/tasks/workflows/assignments/{wf_assign}/steps/{phase7_task['step_ids'][0]}/execute",
        json={"status": "in_progress"},
        headers=_auth(alex),
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text
    # still exactly one result row (no duplicates)
    rows = _pg(
        "SELECT COUNT(*) FROM task_results WHERE worker_task_assignment_id = %s", (aid,)
    )
    assert rows[0][0] == 1


def test_reassignment_persists_both_rows(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]

    res = client.post(
        f"/api/v1/supervisor/tasks/{aid}/reassign",
        json={"new_worker_profile_id": JORDAN, "reason": "skill match"},
        headers=_auth(sup),
    )
    assert res.status_code == 200, res.text
    new_id = res.json()["new_assignment"]["id"]

    old_row = _pg("SELECT status FROM worker_task_assignments WHERE id = %s", (aid,))
    new_row = _pg(
        "SELECT status, worker_profile_id FROM worker_task_assignments WHERE id = %s",
        (new_id,),
    )
    assert old_row[0][0] == "cancelled", "old assignment must be cancelled, persisted"
    assert new_row[0][0] == "assigned" and str(new_row[0][1]) == JORDAN

    audit = _pg(
        "SELECT 1 FROM audit_events WHERE resource_id = %s "
        "AND event_type = 'supervisor_task_reassigned'",
        (new_id,),
    )
    assert audit

    # reassign a terminal assignment -> 409
    jordan = _login(client, "jordan.worker@amap.com")
    _start(client, jordan, new_id)
    wf_assign = _pg(
        "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (phase7_task["workflow_id"], JORDAN),
    )[0][0]
    _complete_all_steps(client, jordan, wf_assign, phase7_task["step_ids"])
    client.post(
        f"/api/v1/tasks/assignments/{new_id}/complete",
        json={"outcome": "completed"},
        headers=_auth(jordan),
    )
    res = client.post(
        f"/api/v1/supervisor/tasks/{new_id}/reassign",
        json={"new_worker_profile_id": ALEX},
        headers=_auth(sup),
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text


# ---------------------------------------------------------------------------
# Honest supervisor telemetry (progress/step/health from real rows)
# ---------------------------------------------------------------------------

def test_supervisor_telemetry_is_real(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    alex = _login(client, "alex.worker@amap.com")

    # readiness row for alex: two of three modalities validated
    # (save any pre-existing row so cleanup restores exact prior state)
    prior_ready = _pg(
        "SELECT is_fresher, onboarding_completed, readiness_status, interaction_mode, "
        "gesture_ready, voice_ready, multimodal_ready, task_training_complete, "
        "overall_ready, completed_stages, active_preferences "
        "FROM worker_readiness WHERE worker_profile_id = %s",
        (ALEX,),
    )
    _pg(
        "INSERT INTO worker_readiness (worker_profile_id, is_fresher, onboarding_completed, "
        "readiness_status, interaction_mode, gesture_ready, voice_ready, multimodal_ready, "
        "task_training_complete, overall_ready, completed_stages, active_preferences) "
        "VALUES (%s, false, true, 'ready', 'gesture', true, false, true, true, true, "
        "'[]'::jsonb, '{}'::jsonb) "
        "ON CONFLICT (worker_profile_id) DO UPDATE SET "
        "interaction_mode = EXCLUDED.interaction_mode, "
        "gesture_ready = EXCLUDED.gesture_ready, "
        "voice_ready = EXCLUDED.voice_ready, "
        "multimodal_ready = EXCLUDED.multimodal_ready",
        (ALEX,),
    )
    try:
        aid = _assign(client, sup, phase7_task["task_id"], ALEX).json()["assignment"]["id"]
        _start(client, alex, aid)
        wf_assign = _pg(
            "SELECT id FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
            (phase7_task["workflow_id"], ALEX),
        )[0][0]
        # complete exactly 1 of 3 steps
        res = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assign}/steps/{phase7_task['step_ids'][0]}/execute",
            json={"status": "completed"},
            headers=_auth(alex),
        )
        assert res.status_code == 201, res.text

        res = client.get("/api/v1/supervisor/workers", headers=_auth(sup))
        assert res.status_code == 200, res.text
        alex_item = next(w for w in res.json() if w["worker_profile_id"] == ALEX)
        assert alex_item["current_task_id"] == phase7_task["task_id"]
        assert alex_item["current_step_number"] == 2  # step 2 is next
        assert alex_item["current_step_title"] == STEP_NAMES[1]
        assert alex_item["total_steps"] == 3
        assert abs(alex_item["progress_percent"] - 33.3) < 0.2
        # health flags mirror the readiness table exactly (not hardcoded True)
        assert alex_item["interaction_health"] == {
            "gesture_ready": True,
            "voice_ready": False,
            "multimodal_ready": True,
        }
        assert alex_item["interaction_mode"] == "gesture"

        # worker WITHOUT a readiness row must not claim ready modalities
        jordan_item = next(w for w in res.json() if w["worker_profile_id"] == JORDAN)
        # (jordan may have a default row from onboarding tests; assert against DB)
        db_ready = _pg(
            "SELECT gesture_ready, voice_ready, multimodal_ready "
            "FROM worker_readiness WHERE worker_profile_id = %s",
            (JORDAN,),
        )
        expected = (
            {
                "gesture_ready": bool(db_ready[0][0]),
                "voice_ready": bool(db_ready[0][1]),
                "multimodal_ready": bool(db_ready[0][2]),
            }
            if db_ready
            else {"gesture_ready": False, "voice_ready": False, "multimodal_ready": False}
        )
        assert jordan_item["interaction_health"] == expected

        # worker detail: step details reflect real executions
        res = client.get(f"/api/v1/supervisor/workers/{ALEX}", headers=_auth(sup))
        assert res.status_code == 200, res.text
        detail = res.json()
        assert detail["step_details"][0]["status"] == "completed"
        assert detail["step_details"][1]["is_current"] is True
        assert detail["step_details"][2]["status"] == "pending"
    finally:
        if prior_ready:
            p = prior_ready[0]
            import json as _json

            _pg(
                "UPDATE worker_readiness SET is_fresher=%s, onboarding_completed=%s, "
                "readiness_status=%s, interaction_mode=%s, gesture_ready=%s, "
                "voice_ready=%s, multimodal_ready=%s, task_training_complete=%s, "
                "overall_ready=%s, completed_stages=%s::jsonb, "
                "active_preferences=%s::jsonb, updated_at=CURRENT_TIMESTAMP "
                "WHERE worker_profile_id=%s",
                (
                    p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8],
                    _json.dumps(p[9]), _json.dumps(p[10]), ALEX,
                ),
            )
        else:
            _pg("DELETE FROM worker_readiness WHERE worker_profile_id = %s", (ALEX,))


def test_dashboard_kpis_match_sql(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    res = client.get("/api/v1/supervisor/dashboard", headers=_auth(sup))
    assert res.status_code == 200, res.text
    body = res.json()

    completed, in_prog, failed = _pg(
        """
        SELECT
            COUNT(*) FILTER (WHERE a.status = 'completed'),
            COUNT(*) FILTER (WHERE a.status IN ('in_progress', 'assigned')),
            COUNT(*) FILTER (WHERE a.status IN ('failed', 'cancelled'))
        FROM worker_task_assignments a
        JOIN tasks t ON t.id = a.task_id
        WHERE t.organization_id = %s
        """,
        (ORG,),
    )[0]
    assert body["completed_tasks_count"] == completed
    assert body["in_progress_tasks_count"] == in_prog
    assert body["failed_tasks_count"] == failed


def test_assignable_tasks_list_is_org_scoped(client, phase7_task):
    sup = _login(client, "supervisor@amap.com")
    res = client.get("/api/v1/supervisor/tasks", headers=_auth(sup))
    assert res.status_code == 200, res.text
    ids = [t["id"] for t in res.json()]
    assert phase7_task["task_id"] in ids
    # every listed task is a real active row in this org
    rows = _pg(
        "SELECT id FROM tasks WHERE organization_id = %s AND status = 'active'", (ORG,)
    )
    db_ids = {str(r[0]) for r in rows}
    assert set(ids) <= db_ids, "list must not contain fabricated tasks"
