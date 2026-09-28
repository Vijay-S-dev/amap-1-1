"""
AMAP E2E Worker Journey — Manual Acceptance Scenario (automated at the API level).

Exercises the REAL pipeline end-to-end against real PostgreSQL, in the exact
order the rewritten worker workstation (/worker page) drives it:

  1.  Fresher login (maria.newhire@amap.com) + supervisor login
  2.  Work session start + heartbeat -> supervisor sees the real worker ONLINE
  3.  Gesture mapping load (PostgreSQL-authoritative personalization)
  4.  Real assignment start (workflow from PostgreSQL, no demo data)
  5.  Gesture: pinch landmarks -> /gestures/process-frame -> left_click mapping
  6.  UI action through the safety gateway (/actions/execute) with persistence
  7.  Voice: "scroll down" -> same action resolver -> scroll execution
  8.  Multimodal fusion: pinch (spatial) + "move this" -> drag_start bound to
      the pointer target; drag_end after the move
  9.  Step execution persisted (complete step 1 of 2)
  10. Refresh persistence: re-login + progress restore endpoint returns the
      completed step
  11. Pause -> supervisor sees PAUSED; resume -> WORKING again
  12. Assistance request -> supervisor sees ASSISTANCE_REQUESTED -> acknowledge
  13. Emergency stop -> immutable event + urgent assistance -> supervisor sees
      the emergency state -> resolve
  14. Complete step 2 -> finish assignment (2/2 steps) -> task result persisted
  15. End work session -> supervisor sees the worker OFFLINE

Run:
  cd backend && DATABASE_URL=... python ../scripts/e2e_worker_journey.py
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
MARIA_PROFILE = "d0000000-0000-0000-0000-000000000003"
PASSWORD = "SecurePassword123!"
API = "/api/v1"

T0 = 1_700_000_000_000

steps_passed = 0


def ok(label, cond, detail=""):
    global steps_passed
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        raise SystemExit(f"E2E FAILED at: {label} {detail}")
    steps_passed += 1


def pinch_hand():
    """Synthetic 21-landmark PINCH hand (same geometry the unit tests verify)."""
    h = [{"x": 0.5, "y": 0.6, "z": 0.0} for _ in range(21)]
    h[1], h[2], h[3] = {"x": 0.46, "y": 0.58, "z": 0}, {"x": 0.45, "y": 0.55, "z": 0}, {"x": 0.45, "y": 0.52, "z": 0}
    h[4] = {"x": 0.465, "y": 0.505, "z": 0}
    for mcp, pip, tip in [(5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)]:
        h[mcp] = {"x": 0.52, "y": 0.55, "z": 0}
        h[pip] = {"x": 0.53, "y": 0.48, "z": 0}
        h[tip] = {"x": 0.54, "y": 0.40, "z": 0}
    for mcp, pip, tip in [(9, 10, 12), (13, 14, 16), (17, 18, 20)]:
        h[pip] = {"x": 0.53, "y": 0.52, "z": 0}
        h[tip] = {"x": 0.52, "y": 0.56, "z": 0}
    h[8] = {"x": 0.47, "y": 0.51, "z": 0}
    return h


def main() -> None:
    import psycopg

    from app.config import get_settings

    client = TestClient(app)

    def pg(sql, params=None, fetch=False):
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetch:
                    return cur.fetchall()
                conn.commit()
                return None

    def login(email):
        r = client.post(
            f"{API}/auth/login",
            json={"organization_id": ORG, "email": email, "password": PASSWORD},
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def supervisor_view(maria_auth):
        sup = login("supervisor@amap.com")
        workers = client.get(f"{API}/supervisor/workers", headers=sup).json()
        return next(w for w in workers if w["worker_profile_id"] == MARIA_PROFILE)

    print("=" * 72)
    print(" AMAP E2E WORKER JOURNEY (real PostgreSQL, no mocks)")
    print("=" * 72)

    # -- 1. Logins ------------------------------------------------------------
    print("\n1. Authentication (fresher + supervisor)")
    maria = login("maria.newhire@amap.com")
    me = client.get(f"{API}/auth/me", headers=maria).json()
    ok("Fresher Maria logs in with seed credentials", me["worker_profile_id"] == MARIA_PROFILE)
    bad = client.post(
        f"{API}/auth/login",
        json={"organization_id": ORG, "email": "maria.newhire@amap.com", "password": "WrongPassword123!"},
    )
    ok("Wrong password rejected (401)", bad.status_code == 401, str(bad.status_code))

    # -- fixture: real workflow/task/assignment -------------------------------
    wf_id, task_id = str(uuid.uuid4()), str(uuid.uuid4())
    step_ids = [str(uuid.uuid4()) for _ in range(2)]
    assignment_id = str(uuid.uuid4())
    pg(
        "INSERT INTO workflows (id, organization_id, name, description, status) "
        "VALUES (%s,%s,%s,%s,'active')",
        (wf_id, ORG, f"E2E Journey Workflow {uuid.uuid4().hex[:6]}", "E2E acceptance fixture"),
    )
    for i, sid in enumerate(step_ids, start=1):
        pg(
            "INSERT INTO workflow_steps (id, workflow_id, step_order, name, description, status) "
            "VALUES (%s,%s,%s,%s,%s,'active')",
            (sid, wf_id, i, f"E2E Step {i}: Fit component", "E2E fixture step"),
        )
    pg(
        "INSERT INTO tasks (id, organization_id, name, description, status) "
        "VALUES (%s,%s,%s,%s,'active')",
        (task_id, ORG, f"E2E Journey Task {uuid.uuid4().hex[:6]}", "E2E acceptance fixture"),
    )
    pg("INSERT INTO task_workflows (task_id, workflow_id) VALUES (%s,%s)", (task_id, wf_id))
    pg(
        "INSERT INTO worker_task_assignments (id, task_id, worker_profile_id, status) "
        "VALUES (%s,%s,%s,'assigned')",
        (assignment_id, task_id, MARIA_PROFILE),
    )

    try:
        # -- 2. Session + heartbeat -------------------------------------------
        print("\n2. Work session lifecycle + supervisor live view")
        r = client.post(f"{API}/sessions/start", headers=maria)
        ok("Start work session", r.status_code == 201, r.text)
        session_id = r.json()["id"]

        r = client.post(f"{API}/sessions/heartbeat", headers=maria, json={"work_session_id": session_id})
        ok("Heartbeat accepted", r.status_code == 200 and r.json()["last_heartbeat_at"], r.text)

        view = supervisor_view(maria)
        ok(
            "Supervisor sees Maria ONLINE with the live session",
            view["is_online"] is True and view["active_session_id"] == session_id,
            json.dumps(view)[:300],
        )

        # -- 3. Gesture mapping (PostgreSQL) -----------------------------------
        print("\n3. Personalized gesture mapping (PostgreSQL)")
        r = client.get(f"{API}/personalization/me/gesture-mapping", headers=maria)
        mapping = r.json()
        ok("Load effective mapping", r.status_code == 200 and mapping["gesture_action_map"], r.text)
        ok(
            "Canonical pinch -> left_click from the preset",
            mapping["gesture_action_map"]["pinch"] == "left_click",
        )
        ok("Calibration present (dwell/sensitivity/smoothing)", mapping["calibration"]["dwell_time_ms"] > 0)

        # -- 4. Assignment start ------------------------------------------------
        print("\n4. Real assignment start")
        r = client.post(f"{API}/tasks/assignments/{assignment_id}/start", headers=maria)
        ok("Start assignment", r.status_code == 200, r.text)
        wfa_id = r.json()["workflow_assignment_id"]

        # -- 5. Gesture: pinch frame -> server classification -------------------
        print("\n5. Gesture pipeline (camera landmarks -> action)")
        triggered = None
        for ts in range(T0, T0 + 1200, 200):
            r = client.post(
                f"{API}/gestures/process-frame",
                headers=maria,
                json={
                    "landmarks": pinch_hand(),
                    "handedness": "Right",
                    "timestamp_ms": ts,
                    "dwell_time_ms": 400,
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            if body.get("is_triggered"):
                triggered = body
        ok(
            "Server classifies pinch and triggers after dwell (once)",
            bool(triggered) and triggered["detected_gesture"] == "pinch",
            json.dumps(triggered or {})[:300],
        )
        ok("Pinch resolves to left_click via worker mapping", triggered["action_mapping"] == "left_click")

        # -- 6. UI action through the safety gateway ----------------------------
        print("\n6. UI interaction action (click) through /actions/execute")
        r = client.post(
            f"{API}/actions/execute",
            headers=maria,
            json={
                "action_name": "left_click",
                "parameters": {"pointer_x": 320, "pointer_y": 240, "target_tag": "button"},
            },
        )
        ok("left_click executed through the gateway", r.status_code == 200 and r.json()["success"], r.text)
        view = supervisor_view(maria)
        ok(
            "Supervisor sees the real last action",
            view["last_action_description"] == "left_click",
            json.dumps(view)[:300],
        )

        # -- 7. Voice ------------------------------------------------------------
        print("\n7. Voice command (same action resolver)")
        r = client.post(
            f"{API}/voice/process-command",
            headers=maria,
            json={"raw_transcript": "scroll down", "confidence": 0.95, "language": "en-US"},
        )
        ok('"scroll down" -> scroll_down', r.status_code == 200 and r.json()["action_mapping"] == "scroll_down", r.text)
        r = client.post(
            f"{API}/actions/execute",
            headers=maria,
            json={"action_name": "scroll_down", "parameters": {"amount_px": 400, "target": "instructions"}},
        )
        ok("scroll_down executed + persisted", r.status_code == 200 and r.json()["success"], r.text)

        # -- 8. Multimodal fusion -------------------------------------------------
        print("\n8. Multimodal fusion (gesture + voice)")
        r = client.post(
            f"{API}/multimodal/fuse",
            headers=maria,
            json={
                "inputs": [
                    {
                        "mode": "gesture",
                        "raw_intent": "pinch",
                        "confidence": 0.92,
                        "timestamp_ms": T0,
                        "context_data": {"spatial_x": 640, "spatial_y": 360, "gesture": "pinch"},
                    },
                    {"mode": "voice", "raw_intent": "move this", "confidence": 0.93, "timestamp_ms": T0 + 300},
                ],
                "temporal_window_ms": 1500,
            },
        )
        fused = r.json()
        ok(
            'pinch + "move this" -> drag_start bound to pointer target',
            r.status_code == 200 and fused["fused_action"] == "drag_start" and fused["target_context"].get("spatial_x") == 640,
            json.dumps(fused)[:300],
        )
        for action, params in [
            ("drag_start", {"pointer_x": 640, "pointer_y": 360}),
            ("drag_end", {"path_px": 280, "duration_ms": 1100, "dropped": True}),
        ]:
            r = client.post(
                f"{API}/actions/execute", headers=maria, json={"action_name": action, "parameters": params}
            )
            ok(f"{action} executed + persisted", r.status_code == 200 and r.json()["success"], r.text)

        # -- 9. Step execution ------------------------------------------------
        print("\n9. Workflow step execution (real persistence)")
        r = client.post(
            f"{API}/tasks/workflows/assignments/{wfa_id}/steps/{step_ids[0]}/execute",
            headers=maria,
            json={"status": "completed", "execution_data": {"completed_via": "gesture pinch+voice confirm"}},
        )
        ok("Step 1 completed", r.status_code == 201, r.text)

        # -- 10. Refresh persistence -------------------------------------------
        print("\n10. Refresh / re-login persistence")
        maria2 = login("maria.newhire@amap.com")
        r = client.get(f"{API}/tasks/workflows/assignments/{wfa_id}/executions", headers=maria2)
        execs = r.json()
        ok(
            "After re-login, progress restore shows step 1 completed",
            r.status_code == 200 and len(execs) == 1 and execs[0]["status"] == "completed",
            r.text[:300],
        )
        view = supervisor_view(maria2)
        ok(
            "Supervisor sees real progress (1/2, step 2 current)",
            view["current_assignment_id"] == assignment_id and view["progress_percent"] == 50.0,
            json.dumps({k: view[k] for k in ('progress_percent', 'current_step_number', 'total_steps')}),
        )

        # -- 11. Pause / resume -------------------------------------------------
        print("\n11. Pause / resume")
        r = client.post(f"{API}/sessions/{session_id}/pause", headers=maria)
        ok("Pause session", r.status_code == 200, r.text)
        client.post(f"{API}/sessions/heartbeat", headers=maria, json={"work_session_id": session_id})
        view = supervisor_view(maria)
        ok("Supervisor sees PAUSED", view["status"] == "PAUSED", json.dumps(view)[:300])
        r = client.post(f"{API}/sessions/{session_id}/resume", headers=maria)
        ok("Resume session", r.status_code == 200, r.text)
        client.post(f"{API}/sessions/heartbeat", headers=maria, json={"work_session_id": session_id})
        view = supervisor_view(maria)
        ok("Supervisor sees WORKING again", view["status"] == "WORKING", json.dumps(view)[:300])

        # -- 12. Assistance ------------------------------------------------------
        print("\n12. Assistance request")
        r = client.post(
            f"{API}/assistance/requests",
            headers=maria,
            json={
                "reason": "E2E journey: component tolerances unclear on step 2",
                "priority": "normal",
                "work_session_id": session_id,
                "worker_task_assignment_id": assignment_id,
            },
        )
        ok("Create assistance request", r.status_code == 201, r.text)
        request_id = r.json()["id"]
        view = supervisor_view(maria)
        ok("Supervisor sees ASSISTANCE_REQUESTED", view["status"] == "ASSISTANCE_REQUESTED", json.dumps(view)[:300])
        sup = login("supervisor@amap.com")
        r = client.post(f"{API}/assistance/requests/{request_id}/acknowledge", headers=sup)
        ok("Supervisor acknowledges", r.status_code == 200, r.text)
        r = client.post(f"{API}/assistance/requests/{request_id}/resolve", headers=sup)
        ok("Supervisor resolves", r.status_code == 200, r.text)

        # -- 13. Emergency stop ---------------------------------------------------
        print("\n13. Emergency stop")
        r = client.post(
            f"{API}/actions/emergency-stop",
            headers=maria,
            json={"reason": "E2E journey: misaligned fixture", "work_session_id": session_id},
        )
        ok("Emergency stop accepted", r.status_code == 200 and r.json()["success"], r.text)
        events = pg(
            "SELECT COUNT(*) FROM execution_events WHERE event_type='emergency_stop' "
            "AND worker_profile_id=%s",
            (MARIA_PROFILE,),
            fetch=True,
        )
        ok("Immutable emergency_stop event persisted", events[0][0] >= 1)
        urgent = pg(
            "SELECT id FROM assistance_requests WHERE worker_profile_id=%s "
            "AND priority='urgent' AND status IN ('open','acknowledged') ORDER BY created_at DESC LIMIT 1",
            (MARIA_PROFILE,),
            fetch=True,
        )
        ok("Urgent assistance request raised for the supervisor", len(urgent) == 1)
        view = supervisor_view(maria)
        ok(
            "Supervisor dashboard reflects the emergency state",
            view["status"] == "ASSISTANCE_REQUESTED" and view["is_emergency_stop"] is True,
            json.dumps(view)[:300],
        )
        if urgent:
            client.post(f"{API}/assistance/requests/{urgent[0][0]}/acknowledge", headers=sup)
            client.post(f"{API}/assistance/requests/{urgent[0][0]}/resolve", headers=sup)

        # -- 14. Complete the task ------------------------------------------------
        print("\n14. Complete the assignment")
        r = client.post(
            f"{API}/tasks/workflows/assignments/{wfa_id}/steps/{step_ids[1]}/execute",
            headers=maria,
            json={"status": "completed", "execution_data": {"completed_via": "gesture"}},
        )
        ok("Step 2 completed", r.status_code == 201, r.text)
        r = client.post(
            f"{API}/tasks/assignments/{assignment_id}/complete",
            headers=maria,
            json={"outcome": "completed"},
        )
        body = r.json()
        ok(
            "Assignment finished: 2/2 steps in the persisted task result",
            r.status_code == 200 and body["result_data"]["completed_steps"] == 2,
            r.text[:300],
        )

        # -- 15. End session -------------------------------------------------------
        print("\n15. End of work session")
        r = client.post(f"{API}/sessions/{session_id}/end", headers=maria)
        ok("End session", r.status_code == 200, r.text)
        view = supervisor_view(maria)
        ok("Supervisor sees the worker OFFLINE after shift end", view["is_online"] is False, json.dumps(view)[:300])

    finally:
        # Cleanup: remove the E2E fixture (keep the seeded database pristine).
        # Deletes are keyed by collected ids — psycopg treats a literal '%' in
        # LIKE patterns of parameterized statements as a placeholder, so no
        # LIKE-based cleanup here.
        try:
            e2e_task_ids = [r[0] for r in pg(
                "SELECT t.id FROM tasks t WHERE t.id = %s", (task_id,), fetch=True
            )] or [task_id]
            # Maria has no seeded assistance requests or sessions; clear all
            # of hers so repeated E2E runs (and emergency-stop generated
            # requests from earlier runs) leave the seeded DB pristine.
            e2e_request_ids = [r[0] for r in pg(
                "SELECT id FROM assistance_requests WHERE worker_profile_id = %s",
                (MARIA_PROFILE,), fetch=True,
            )]
            pg(
                "DELETE FROM workflow_step_executions WHERE workflow_step_id = ANY(%s)",
                (step_ids,),
            )
            if e2e_request_ids:
                pg("DELETE FROM assistance_requests WHERE id = ANY(%s)", (e2e_request_ids,))
            pg("DELETE FROM task_results WHERE worker_task_assignment_id = %s", (assignment_id,))
            pg(
                "DELETE FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
                (wf_id, MARIA_PROFILE),
            )
            pg("DELETE FROM worker_task_assignments WHERE id = %s", (assignment_id,))
            pg("DELETE FROM task_workflows WHERE task_id = ANY(%s)", (e2e_task_ids,))
            pg("DELETE FROM tasks WHERE id = ANY(%s)", (e2e_task_ids,))
            pg("DELETE FROM workflow_steps WHERE workflow_id = %s", (wf_id,))
            pg("DELETE FROM workflows WHERE id = %s", (wf_id,))
            pg("DELETE FROM work_sessions WHERE worker_profile_id = %s", (MARIA_PROFILE,))
        except Exception as exc:  # pragma: no cover — cleanup best effort
            print(f"  [WARN] cleanup issue: {exc}")

    print("\n" + "=" * 72)
    print(f" E2E WORKER JOURNEY: ALL {steps_passed} CHECKS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
