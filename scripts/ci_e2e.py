"""CI critical end-to-end checks over real HTTP against a running backend.

Intended usage (see .github/workflows/ci.yml):
    uvicorn app.main:app --port 8000 --app-dir backend &
    python scripts/ci_e2e.py

Requires DATABASE_URL (fresh, migrated + seeded database) for the
PostgreSQL persistence assertions.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("CI_E2E_BASE_URL", "http://127.0.0.1:8000")
ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
WORKER = "alex.worker@amap.com"
ADMIN = "admin@amap.com"
SUPERVISOR = "supervisor@amap.com"
PASSWORD = "SecurePassword123!"
DSN = os.environ.get("DATABASE_URL", "")
T0 = 1700000000000

checks: list[tuple[str, bool, str]] = []


def call(method: str, path: str, token: str | None = None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, (json.loads(raw) if raw else None)
        except Exception:
            return exc.code, raw
    except Exception as exc:  # noqa: BLE001 - surfaced as a failed check
        return 0, str(exc)


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + ("" if ok else f" ({detail})"))


def pg(sql: str, params=None):
    import psycopg

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


def main() -> int:
    if not DSN:
        print("DATABASE_URL is required")
        return 2

    # 1. health
    st, body = call("GET", "/api/v1/health")
    check("health", st == 200 and body.get("status") == "ok", f"{st} {body}")

    # 2. login (valid + invalid password + roles)
    st, ok = call(
        "POST",
        "/api/v1/auth/login",
        body={"organization_id": ORG, "email": WORKER, "password": PASSWORD},
    )
    worker_token = ok.get("access_token") if st == 200 else None
    check("worker login", bool(worker_token), f"{st}")

    st, _ = call(
        "POST",
        "/api/v1/auth/login",
        body={"organization_id": ORG, "email": WORKER, "password": "wrong-password"},
    )
    check("invalid password rejected", st in (400, 401, 403), f"{st}")

    st, adm = call(
        "POST",
        "/api/v1/auth/login",
        body={"organization_id": ORG, "email": ADMIN, "password": PASSWORD},
    )
    admin_token = adm.get("access_token") if st == 200 else None
    check("admin login", bool(admin_token), f"{st}")

    st, sup = call(
        "POST",
        "/api/v1/auth/login",
        body={"organization_id": ORG, "email": SUPERVISOR, "password": PASSWORD},
    )
    supervisor_token = sup.get("access_token") if st == 200 else None
    check("supervisor login", bool(supervisor_token), f"{st}")

    # 3. RBAC: worker denied admin-only route; anonymous denied
    st, _ = call("GET", "/api/v1/admin/users", worker_token)
    check("worker denied admin route", st == 403, f"{st}")
    st, _ = call("GET", "/api/v1/admin/users")
    check("anonymous denied admin route", st in (401, 403), f"{st}")

    # 4. voice command intent pipeline (text level, no STT needed)
    st, cmd = call(
        "POST",
        "/api/v1/voice/process-command",
        worker_token,
        {"raw_transcript": "confirm", "confidence": 0.95, "language": "en-US"},
    )
    check(
        "voice command 'confirm' -> confirm_action",
        st == 200 and cmd.get("action_mapping") == "confirm_action",
        f"{st} {cmd}",
    )

    # 5. multimodal fusion (single, reinforcing, conflict, rejected)
    st, fus = call(
        "POST",
        "/api/v1/multimodal/fuse",
        worker_token,
        {
            "inputs": [
                {"mode": "voice", "raw_intent": "confirm_action", "confidence": 0.95, "timestamp_ms": T0}
            ],
            "temporal_window_ms": 1500,
        },
    )
    check("fusion voice-only", st == 200 and fus.get("fused_action") == "confirm_action", f"{st} {fus}")

    st, fus = call(
        "POST",
        "/api/v1/multimodal/fuse",
        worker_token,
        {
            "inputs": [
                {"mode": "voice", "raw_intent": "confirm", "confidence": 0.95, "timestamp_ms": T0},
                {"mode": "gesture", "raw_intent": "thumbs_up", "confidence": 0.90, "timestamp_ms": T0 + 120},
            ],
            "temporal_window_ms": 1500,
        },
    )
    check(
        "fusion reinforcing",
        st == 200 and fus.get("fusion_strategy") == "reinforcing" and fus.get("fused_action") == "confirm_action",
        f"{st} {fus}",
    )

    st, fus = call(
        "POST",
        "/api/v1/multimodal/fuse",
        worker_token,
        {
            "inputs": [
                {"mode": "voice", "raw_intent": "xyzzy invalid command", "confidence": 0.9, "timestamp_ms": T0}
            ],
            "temporal_window_ms": 1500,
        },
    )
    check("fusion rejects invalid", st == 200 and fus.get("fused_action") is None, f"{st} {fus}")

    # 6. authorization gateway -> execution_events row in PostgreSQL
    st, ex = call(
        "POST",
        "/api/v1/actions/execute",
        worker_token,
        {"action_name": "confirm_action", "parameters": {"source": "ci-e2e"}},
    )
    rows = pg(
        "SELECT COUNT(*) FROM execution_events WHERE event_type = 'action.confirm_action.executed'"
    )
    check("action executed", st == 200 and ex.get("success") is True, f"{st} {ex}")
    check("execution_events row exists", bool(rows and rows[0][0] >= 1), f"{rows}")

    # 7. department CRUD -> PostgreSQL
    st, dept = call(
        "POST",
        "/api/v1/organizations/manage/departments",
        admin_token,
        {"name": "CI E2E Department", "status": "active"},
    )
    dept_id = dept.get("id") if isinstance(dept, dict) else None
    check("department created", st == 201 and dept_id, f"{st} {dept}")
    found = pg("SELECT status FROM departments WHERE id = %s", (dept_id,))
    check("department row in PostgreSQL", bool(found), f"{found}")
    st, _ = call("DELETE", f"/api/v1/organizations/manage/departments/{dept_id}", admin_token)
    after = pg("SELECT status FROM departments WHERE id = %s", (dept_id,))
    check(
        "department soft-deleted (inactive)",
        st == 200 and after and after[0][0] == "inactive",
        f"{st} {after}",
    )
    pg("DELETE FROM departments WHERE id = %s", (dept_id,))

    # 8. accessibility preference persisted to PostgreSQL
    st, _ = call("GET", "/api/v1/accessibility/preferences", admin_token)
    st2, _ = call(
        "PUT",
        "/api/v1/accessibility/preferences",
        admin_token,
        {"preferences": {"highContrast": True, "language": "en"}},
    )
    pref_row = pg(
        "SELECT preferences FROM user_accessibility_preferences "
        "WHERE user_id = (SELECT id FROM users WHERE email = %s)",
        (ADMIN,),
    )
    prefs_ok = bool(pref_row) and isinstance(pref_row[0][0], dict) and pref_row[0][0].get("highContrast") is True
    check("accessibility preference persisted", st in (200, 404) and st2 == 200 and prefs_ok, f"{st}/{st2} {pref_row}")

    # 9. audit trail populated with real actors
    audit = pg(
        "SELECT COUNT(*) FROM audit_events WHERE actor_user_id IS NOT NULL"
    )
    check("audit_events have real actors", bool(audit and audit[0][0] >= 1), f"{audit}")

    # 10. supervisor dashboard & worker telemetry
    st, sup_dash = call("GET", "/api/v1/supervisor/dashboard", supervisor_token)
    check(
        "supervisor dashboard real metrics",
        st == 200 and isinstance(sup_dash, dict) and "total_workers" in sup_dash,
        f"{st} {sup_dash}",
    )

    st, sup_workers = call("GET", "/api/v1/supervisor/workers", supervisor_token)
    check(
        "supervisor worker list",
        st == 200 and isinstance(sup_workers, list) and len(sup_workers) >= 1,
        f"{st} {len(sup_workers) if isinstance(sup_workers, list) else sup_workers}",
    )

    # 11. task assignment & execution lifecycle -> task_results in PostgreSQL
    assignment_id = "61000000-0000-0000-0000-000000000001"
    st, start_res = call(
        "POST",
        f"/api/v1/tasks/assignments/{assignment_id}/start",
        worker_token,
    )
    check("task assignment start", st in (200, 409), f"{st} {start_res}")

    st, comp_res = call(
        "POST",
        f"/api/v1/tasks/assignments/{assignment_id}/complete",
        worker_token,
        {"outcome": "completed", "result_data": {"units_assembled": 1}},
    )
    check("task assignment complete", st in (200, 409), f"{st} {comp_res}")

    res_rows = pg(
        "SELECT outcome FROM task_results WHERE worker_task_assignment_id = %s",
        (assignment_id,),
    )
    check("task_results row in PostgreSQL", bool(res_rows), f"{res_rows}")

    # 12. assistance request lifecycle -> PostgreSQL persistence
    st, req_res = call(
        "POST",
        "/api/v1/assistance/requests",
        worker_token,
        {"reason": "Need torque wrench calibration check", "priority": "normal"},
    )
    req_id = req_res.get("id") if isinstance(req_res, dict) else None
    check("assistance request created", st == 201 and req_id, f"{st} {req_res}")

    if req_id:
        st, _ = call(
            "POST",
            f"/api/v1/supervisor/assistance/{req_id}/resolve",
            supervisor_token,
            {"resolution_notes": "Calibrated tool supplied"},
        )
        check("assistance request resolved by supervisor", st == 200, f"{st}")
        ast_row = pg("SELECT status FROM assistance_requests WHERE id = %s", (req_id,))
        check("assistance_requests status 'resolved' in PostgreSQL", bool(ast_row and ast_row[0][0] == "resolved"), f"{ast_row}")

    # 13. custom gesture training & lifecycle -> custom_gestures in PostgreSQL
    sample_landmarks = [{"x": 0.5 + 0.001 * i, "y": 0.5, "z": 0.0} for i in range(21)]
    five_samples = [sample_landmarks for _ in range(5)]
    st, train_res = call(
        "POST",
        "/api/v1/gestures/custom/train",
        worker_token,
        {
            "gesture_name": "CI Test Custom Gesture",
            "intent": "confirm_action",
            "handedness": "Right",
            "samples": five_samples,
        },
    )
    cg_id = train_res.get("id") if isinstance(train_res, dict) else None
    check("custom gesture trained", st == 201 and cg_id, f"{st} {train_res}")

    if cg_id:
        cg_rows = pg("SELECT gesture_name, status FROM custom_gestures WHERE id = %s", (cg_id,))
        check("custom_gestures row in PostgreSQL", bool(cg_rows and cg_rows[0][1] == "active"), f"{cg_rows}")
        st, del_res = call("DELETE", f"/api/v1/gestures/custom/{cg_id}", worker_token)
        check("custom gesture deleted", st == 200, f"{st} {del_res}")
        cg_after = pg("SELECT status FROM custom_gestures WHERE id = %s", (cg_id,))
        check("custom gesture soft-deleted (deleted)", bool(cg_after and cg_after[0][0] == "deleted"), f"{cg_after}")

    # 14. safety-critical interlock gating & emergency stop
    st, gate_res = call(
        "POST",
        "/api/v1/actions/execute",
        worker_token,
        {"action_name": "unregistered_dangerous_action"},
    )
    check("unregistered action rejected", st in (404, 422), f"{st} {gate_res}")

    st, em_res = call(
        "POST",
        "/api/v1/actions/emergency-stop",
        worker_token,
        {"reason": "E2E safety test interlock"},
    )
    check("emergency stop executed", st == 200 and em_res.get("success") is True, f"{st} {em_res}")
    em_rows = pg("SELECT COUNT(*) FROM execution_events WHERE event_type = 'emergency_stop'")
    check("emergency_stop in PostgreSQL", bool(em_rows and em_rows[0][0] >= 1), f"{em_rows}")

    # 15. cross-organization isolation (tenancy boundary)
    FAKE_ORG = "00000000-0000-0000-0000-000000000099"
    st, bad_login = call(
        "POST",
        "/api/v1/auth/login",
        body={"organization_id": FAKE_ORG, "email": WORKER, "password": PASSWORD},
    )
    check("cross-org authentication rejected", st in (400, 401, 403, 404), f"{st}")

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        for name, _, detail in failed:
            print(f"  FAILED: {name}: {detail}")
        return 1
    print("CI E2E: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
