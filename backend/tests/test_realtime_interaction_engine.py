"""
Real-Time Worker Interaction Engine integration tests (real PostgreSQL).

Covers the implementation added for real-time gesture/voice/multimodal task
execution:

  AUTH
    - Fresher (Maria) / worker / supervisor / admin login; invalid credentials
  ACTIONS
    - New UI-interaction + task-lifecycle actions registered & executable
      through the /actions/execute safety gateway with persistence
  VOICE
    - New command vocabulary parsing (scroll/click/drag/select/task lifecycle)
  GESTURE CLASSIFICATION
    - pinch / two_finger / swipe mapping via the server pipeline
  MULTIMODAL FUSION
    - pinch + "move this" -> drag_start (complementary binding)
    - pointing (spatial) + "select" -> select_item at the pointer target
    - two_finger_move (generic scroll) + "scroll down" -> direction refinement
    - low-confidence rejection and ambiguous conflict safety
  PERSONALIZED GESTURE MAPPING (PostgreSQL-authoritative)
    - GET/PUT /personalization/me/gesture-mapping; overrides change resolution
      for both direct gesture frames and multimodal fusion; survives restart
      (fresh service instance); invalid action rejected
  SESSION LIFECYCLE / SUPERVISOR LIVE VIEW
    - heartbeat marks worker online; supervisor telemetry reflects status,
      last activity and last action; stale heartbeat -> offline; end session
    - ownership: a worker cannot heartbeat another worker's session
  ASSIGNMENT EXECUTION
    - start -> complete_step -> finish_assignment persisted; progress restore
      endpoint returns completed steps (refresh persistence)
"""

import json
from uuid import uuid4

import psycopg
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"  # alex.worker (existing employee)
MARIA = "d0000000-0000-0000-0000-000000000003"  # maria.newhire (fresher)
DEFAULT_PASSWORD = "SecurePassword123!"

T0 = 1700000000000


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


# ---------------------------------------------------------------------------
# AUTH: fresher login root cause + fix
# ---------------------------------------------------------------------------


class TestFresherAndRoleLogins:
    def test_fresher_maria_login_works(self, client):
        """The seeded fresher account (referenced by the login screen) works."""
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": ORG,
                "email": "maria.newhire@amap.com",
                "password": DEFAULT_PASSWORD,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["access_token"]
        me = client.get("/api/v1/auth/me", headers=_auth(body["access_token"]))
        assert me.status_code == 200
        assert "worker" in me.json()["roles"]
        assert me.json()["worker_profile_id"] == MARIA

    def test_fresher_readiness_is_seeded(self, client):
        token = _login(client, "maria.newhire@amap.com")
        resp = client.get(f"/api/v1/workers/{MARIA}/readiness", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_fresher"] is True
        assert body["onboarding_completed"] is False

    @pytest.mark.parametrize(
        "email", ["admin@amap.com", "supervisor@amap.com", "alex.worker@amap.com"]
    )
    def test_role_logins_work(self, client, email):
        resp = client.post(
            "/api/v1/auth/login",
            json={"organization_id": ORG, "email": email, "password": DEFAULT_PASSWORD},
        )
        assert resp.status_code == 200, resp.text

    def test_invalid_password_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": ORG,
                "email": "maria.newhire@amap.com",
                "password": "WrongPassword!",
            },
        )
        assert resp.status_code == 401

    def test_wrong_organization_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": str(uuid4()),
                "email": "maria.newhire@amap.com",
                "password": DEFAULT_PASSWORD,
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# ACTIONS: new canonical actions registered & executable
# ---------------------------------------------------------------------------


class TestNewActionRegistration:
    @pytest.mark.parametrize(
        "action_name",
        [
            "pointer_move",
            "left_click",
            "right_click",
            "double_click",
            "drag_start",
            "drag_end",
            "scroll",
            "scroll_up",
            "scroll_down",
            "select_item",
            "start_assignment",
            "complete_step",
            "finish_assignment",
            "cancel_action",
        ],
    )
    def test_action_registered_in_database(self, action_name):
        rows = _pg("SELECT name, status, category FROM actions WHERE name = %s", (action_name,))
        assert rows, f"Action {action_name} must be registered by migration 052"
        assert rows[0][1] == "active"

    def test_ui_action_executes_through_safety_gateway(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = client.post(
            "/api/v1/actions/execute",
            headers=_auth(token),
            json={
                "action_name": "left_click",
                "parameters": {"pointer_x": 320, "pointer_y": 240, "target_tag": "button"},
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["action_name"] == "left_click"

        # persisted execution event
        events = _pg(
            "SELECT event_type FROM execution_events "
            "WHERE event_type = 'action.left_click.executed' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        assert events, "left_click execution must be persisted"

    def test_drag_and_scroll_actions_persist(self, client):
        token = _login(client, "alex.worker@amap.com")
        for action, params in [
            ("drag_start", {"pointer_x": 100, "pointer_y": 100}),
            ("drag_end", {"path_px": 240, "duration_ms": 900, "dropped": True}),
            ("scroll", {"aggregated": True, "scroll_events": {"down": 4}, "total": 4}),
        ]:
            resp = client.post(
                "/api/v1/actions/execute",
                headers=_auth(token),
                json={"action_name": action, "parameters": params},
            )
            assert resp.status_code == 200, (action, resp.text)

        types = {
            r[0]
            for r in _pg(
                "SELECT DISTINCT event_type FROM execution_events "
                "WHERE event_type LIKE 'action.drag_%' OR event_type = 'action.scroll.executed'"
            )
        }
        assert "action.drag_start.executed" in types
        assert "action.drag_end.executed" in types
        assert "action.scroll.executed" in types

    def test_unregistered_action_rejected(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = client.post(
            "/api/v1/actions/execute",
            headers=_auth(token),
            json={"action_name": "definitely_not_registered_action"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VOICE: new command vocabulary
# ---------------------------------------------------------------------------


class TestVoiceCommandVocabulary:
    @pytest.mark.parametrize(
        "transcript,expected_action",
        [
            ("next step", "next_step"),
            ("previous step", "previous_step"),
            ("complete step", "complete_step"),
            ("confirm", "confirm_action"),
            ("cancel", "cancel_action"),
            ("pause", "pause_session"),
            ("resume", "resume_session"),
            ("scroll up", "scroll_up"),
            ("scroll down", "scroll_down"),
            ("left click", "left_click"),
            ("right click", "right_click"),
            ("double click", "double_click"),
            ("drag", "drag_start"),
            ("move this", "drag_start"),
            ("drop", "drag_end"),
            ("select", "select_item"),
            ("request assistance", "request_assistance"),
            ("start task", "start_assignment"),
            ("finish task", "finish_assignment"),
            ("emergency stop", "emergency_stop"),
            ("stop", "emergency_stop"),
        ],
    )
    def test_voice_command_resolves(self, client, transcript, expected_action):
        token = _login(client, "alex.worker@amap.com")
        resp = client.post(
            "/api/v1/voice/process-command",
            headers=_auth(token),
            json={"raw_transcript": transcript, "confidence": 0.95, "language": "en-US"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["action_mapping"] == expected_action, body

    def test_invalid_voice_command_rejected_with_feedback(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = client.post(
            "/api/v1/voice/process-command",
            headers=_auth(token),
            json={
                "raw_transcript": "make me a sandwich xylophone quadrant",
                "confidence": 0.95,
                "language": "en-US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action_mapping"] is None
        assert body["validation_status"] == "unmatched"
        assert body["message"]


# ---------------------------------------------------------------------------
# GESTURE classification (server pipeline): new poses + mapping
# ---------------------------------------------------------------------------


def _hand(pinch=False, two_finger=False, pointing=False, as_model=False):
    """Synthetic 21-landmark hand for the geometric classifier."""
    from models.gesture import LandmarkPoint

    h = [{"x": 0.5, "y": 0.6, "z": 0.0} for _ in range(21)]
    # thumb
    h[1], h[2], h[3] = {"x": 0.46, "y": 0.58, "z": 0}, {"x": 0.45, "y": 0.55, "z": 0}, {"x": 0.45, "y": 0.52, "z": 0}
    h[4] = {"x": 0.46, "y": 0.50, "z": 0}
    # fingers: extended tips default (open hand)
    for mcp, pip, tip in [(5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)]:
        h[mcp] = {"x": 0.52, "y": 0.55, "z": 0}
        h[pip] = {"x": 0.53, "y": 0.48, "z": 0}
        h[tip] = {"x": 0.54, "y": 0.40, "z": 0}
    if pinch:
        # curl middle/ring/pinky, thumb tip meets index tip
        for mcp, pip, tip in [(9, 10, 12), (13, 14, 16), (17, 18, 20)]:
            h[pip] = {"x": 0.53, "y": 0.52, "z": 0}
            h[tip] = {"x": 0.52, "y": 0.56, "z": 0}
        h[8] = {"x": 0.47, "y": 0.51, "z": 0}
        h[4] = {"x": 0.465, "y": 0.505, "z": 0}
    if two_finger:
        # curl ring/pinky, keep index+middle extended
        for mcp, pip, tip in [(13, 14, 16), (17, 18, 20)]:
            h[pip] = {"x": 0.53, "y": 0.52, "z": 0}
            h[tip] = {"x": 0.52, "y": 0.56, "z": 0}
    if pointing:
        # curl middle/ring/pinky, index extended
        for mcp, pip, tip in [(9, 10, 12), (13, 14, 16), (17, 18, 20)]:
            h[pip] = {"x": 0.53, "y": 0.52, "z": 0}
            h[tip] = {"x": 0.52, "y": 0.56, "z": 0}
        h[4] = {"x": 0.47, "y": 0.53, "z": 0}  # thumb alongside
    if as_model:
        return [LandmarkPoint(**pt) for pt in h]
    return h


class TestServerGestureClassification:
    def test_pinch_classified(self):
        from services.gesture_service import GestureService

        svc = GestureService()
        gesture, conf, is_custom, _ = svc.classify_landmarks(_hand(pinch=True, as_model=True))
        assert gesture == "pinch"
        assert conf >= 0.75

    def test_two_finger_classified(self):
        from services.gesture_service import GestureService

        svc = GestureService()
        gesture, conf, *_ = svc.classify_landmarks(_hand(two_finger=True, as_model=True))
        assert gesture == "two_finger"
        assert conf >= 0.75

    def test_pinch_maps_to_left_click(self):
        from services.gesture_service import GestureService

        svc = GestureService()
        result = svc.process_frame(
            payload=__import__("models.gesture", fromlist=["GestureFramePayload"]).GestureFramePayload(
                landmarks=_hand(pinch=True, as_model=True), handedness="Right", timestamp_ms=T0, dwell_time_ms=100
            ),
            worker_profile_id=None,
        )
        assert result.detected_gesture == "pinch"
        assert result.action_mapping == "left_click"

    def test_pinch_dwell_triggers_once(self):
        from models.gesture import GestureFramePayload
        from services.gesture_service import GestureService

        svc = GestureService()
        triggered = 0
        for ts in range(T0, T0 + 1000, 100):
            r = svc.process_frame(
                payload=GestureFramePayload(
                    landmarks=_hand(pinch=True), handedness="Right", timestamp_ms=ts, dwell_time_ms=200
                ),
                worker_profile_id=None,
            )
            if r.is_triggered:
                triggered += 1
        assert triggered == 1, "one continuous pinch hold must fire exactly once (debounce)"


# ---------------------------------------------------------------------------
# MULTIMODAL FUSION: gesture + voice combinations
# ---------------------------------------------------------------------------


def _fuse(client, token, inputs, window=1500):
    return client.post(
        "/api/v1/multimodal/fuse",
        headers=_auth(token),
        json={"inputs": inputs, "temporal_window_ms": window},
    )


class TestMultimodalFusionCombinations:
    def test_pinch_plus_move_this_binds_drag_to_pointer(self, client):
        """Gesture: pinch at element. Voice: 'move this'. Result: drag_start
        bound to the pointed position (complementary fusion)."""
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {
                    "mode": "gesture",
                    "raw_intent": "pinch",
                    "confidence": 0.92,
                    "timestamp_ms": T0,
                    "context_data": {"spatial_x": 320, "spatial_y": 240, "gesture": "pinch"},
                },
                {
                    "mode": "voice",
                    "raw_intent": "move this",
                    "confidence": 0.93,
                    "timestamp_ms": T0 + 300,
                },
            ],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fused_action"] == "drag_start", body
        assert body["validation_status"] == "valid"
        # spatial context carried through for execution at the pointer
        assert body["target_context"].get("spatial_x") == 320

    def test_pointing_plus_select_binds_select_to_pointer(self, client):
        """Gesture: hand over element. Voice: 'select'. Result: select_item
        with the pointer coordinates as target context."""
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {
                    "mode": "gesture",
                    "raw_intent": "pointing",
                    "confidence": 0.9,
                    "timestamp_ms": T0,
                    "context_data": {"spatial_x": 150, "spatial_y": 400, "gesture": "pointing"},
                },
                {
                    "mode": "voice",
                    "raw_intent": "select",
                    "confidence": 0.94,
                    "timestamp_ms": T0 + 200,
                },
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fused_action"] == "select_item", body
        assert body["target_context"].get("spatial_x") == 150

    def test_two_finger_scroll_plus_voice_direction_refines(self, client):
        """Gesture: two-finger scroll movement (generic). Voice: 'scroll down'.
        Result: direction-refined scroll_down instead of ambiguous conflict."""
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {
                    "mode": "gesture",
                    "raw_intent": "two_finger_move",
                    "confidence": 0.88,
                    "timestamp_ms": T0,
                },
                {
                    "mode": "voice",
                    "raw_intent": "scroll down",
                    "confidence": 0.92,
                    "timestamp_ms": T0 + 250,
                },
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fused_action"] == "scroll_down", body
        assert body["fusion_strategy"] == "direction_refined"

    def test_swipe_up_gesture_resolves_scroll(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {
                    "mode": "gesture",
                    "raw_intent": "swipe_up",
                    "confidence": 0.9,
                    "timestamp_ms": T0,
                }
            ],
        )
        assert resp.status_code == 200
        assert resp.json()["fused_action"] == "scroll_up"

    def test_fist_maps_to_emergency_stop_with_priority(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {"mode": "gesture", "raw_intent": "fist", "confidence": 0.95, "timestamp_ms": T0},
                {
                    "mode": "voice",
                    "raw_intent": "next step",
                    "confidence": 0.9,
                    "timestamp_ms": T0 + 100,
                },
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fused_action"] == "emergency_stop"

    def test_low_confidence_rejected(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [{"mode": "gesture", "raw_intent": "pinch", "confidence": 0.2, "timestamp_ms": T0}],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fused_action"] is None
        assert body["validation_status"] == "rejected"

    def test_conflicting_directions_ambiguous_not_executed(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = _fuse(
            client,
            token,
            [
                {"mode": "gesture", "raw_intent": "swipe_up", "confidence": 0.9, "timestamp_ms": T0},
                {
                    "mode": "voice",
                    "raw_intent": "previous step",
                    "confidence": 0.9,
                    "timestamp_ms": T0 + 100,
                },
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        # Either safely resolved with confirmation or marked ambiguous —
        # never silently executed as the wrong action.
        assert body["fused_action"] is None or body["requires_confirmation"] is True


# ---------------------------------------------------------------------------
# PERSONALIZED GESTURE MAPPING (PostgreSQL)
# ---------------------------------------------------------------------------


@pytest.fixture()
def restore_alex_personalization():
    before = _pg(
        "SELECT personalization_data FROM worker_personalizations WHERE worker_profile_id = %s",
        (ALEX,),
    )
    yield
    if before:
        _pg(
            "UPDATE worker_personalizations SET personalization_data = %s "
            "WHERE worker_profile_id = %s",
            (json.dumps(before[0][0]), ALEX),
        )


class TestPersonalizedGestureMapping:
    def test_get_effective_mapping(self, client):
        token = _login(client, "alex.worker@amap.com")
        resp = client.get("/api/v1/personalization/me/gesture-mapping", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["gesture_action_map"]["pinch"] in ("left_click",)
        assert body["gesture_action_map"]["fist"] == "emergency_stop"
        assert "calibration" in body
        assert body["calibration"]["dwell_time_ms"] > 0

    def test_worker_override_changes_fusion_resolution(self, client, restore_alex_personalization):
        """A worker remaps open_palm to request_assistance; fusion must honor
        the personalized mapping (PostgreSQL, not hardcoded)."""
        token = _login(client, "alex.worker@amap.com")
        resp = client.put(
            "/api/v1/personalization/me/gesture-mapping",
            headers=_auth(token),
            json={
                "gesture_action_map": {"open_palm": "request_assistance"},
                "change_reason": "test remap open_palm",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["gesture_action_map"]["open_palm"] == "request_assistance"
        assert resp.json()["sources"]["open_palm"] == "worker_override"

        fused = _fuse(
            client,
            token,
            [{"mode": "gesture", "raw_intent": "open_palm", "confidence": 0.9, "timestamp_ms": T0}],
        )
        assert fused.status_code == 200
        assert fused.json()["fused_action"] == "request_assistance"

    def test_worker_override_changes_direct_gesture_resolution(
        self, client, restore_alex_personalization
    ):
        from models.gesture import GestureFramePayload
        from services.gesture_service import GestureService

        token = _login(client, "alex.worker@amap.com")
        resp = client.put(
            "/api/v1/personalization/me/gesture-mapping",
            headers=_auth(token),
            json={
                "gesture_action_map": {"pinch": "double_click"},
                "change_reason": "test remap pinch",
            },
        )
        assert resp.status_code == 200, resp.text

        # Fresh service instance == "backend restart": mapping still applies
        svc = GestureService()
        result = svc.process_frame(
            payload=GestureFramePayload(
                landmarks=_hand(pinch=True, as_model=True), handedness="Right", timestamp_ms=T0, dwell_time_ms=100
            ),
            worker_profile_id=__import__("uuid").UUID(ALEX),
        )
        assert result.action_mapping == "double_click", (
            "worker gesture override must survive a fresh service instance (restart)"
        )

    def test_invalid_action_mapping_rejected(self, client, restore_alex_personalization):
        token = _login(client, "alex.worker@amap.com")
        resp = client.put(
            "/api/v1/personalization/me/gesture-mapping",
            headers=_auth(token),
            json={"gesture_action_map": {"pinch": "not_a_real_action"}},
        )
        assert resp.status_code == 422

    def test_calibration_persisted(self, client, restore_alex_personalization):
        token = _login(client, "alex.worker@amap.com")
        resp = client.put(
            "/api/v1/personalization/me/gesture-mapping",
            headers=_auth(token),
            json={
                "calibration": {"cursor_sensitivity": 2.0, "scroll_sensitivity": 300},
                "change_reason": "tune sensitivity",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["calibration"]["cursor_sensitivity"] == 2.0
        assert resp.json()["calibration"]["scroll_sensitivity"] == 300

        # re-login + fresh GET keeps the persisted calibration
        token2 = _login(client, "alex.worker@amap.com")
        get_resp = client.get(
            "/api/v1/personalization/me/gesture-mapping", headers=_auth(token2)
        )
        assert get_resp.json()["calibration"]["cursor_sensitivity"] == 2.0


# ---------------------------------------------------------------------------
# SESSION LIFECYCLE + SUPERVISOR LIVE VIEW
# ---------------------------------------------------------------------------


@pytest.fixture()
def maria_session():
    """Give Maria (fresher, no seeded sessions) a dedicated active session."""
    sid = str(uuid4())
    _pg(
        "INSERT INTO work_sessions (id, organization_id, worker_profile_id, status) "
        "VALUES (%s, %s, %s, 'active')",
        (sid, ORG, MARIA),
    )
    yield sid
    _pg("DELETE FROM work_sessions WHERE id = %s", (sid,))


class TestSessionHeartbeatAndSupervisorView:
    def test_heartbeat_marks_worker_online(self, client, maria_session):
        token = _login(client, "maria.newhire@amap.com")
        resp = client.post(
            "/api/v1/sessions/heartbeat",
            headers=_auth(token),
            json={"work_session_id": maria_session},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["last_heartbeat_at"] is not None

        sup = _login(client, "supervisor@amap.com")
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria = next(w for w in workers if w["worker_profile_id"] == MARIA)
        assert maria["is_online"] is True
        assert maria["status"] in ("WORKING", "AVAILABLE", "PAUSED")
        assert maria["last_activity_at"] is not None
        assert maria["active_session_id"] == maria_session

    def test_stale_heartbeat_shows_offline(self, client, maria_session):
        _pg(
            "UPDATE work_sessions SET last_heartbeat_at = NOW() - INTERVAL '10 minutes', "
            "started_at = NOW() - INTERVAL '10 minutes' WHERE id = %s",
            (maria_session,),
        )
        sup = _login(client, "supervisor@amap.com")
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria = next(w for w in workers if w["worker_profile_id"] == MARIA)
        assert maria["is_online"] is False

    def test_worker_cannot_heartbeat_foreign_session(self, client, maria_session):
        """Authorization: Alex must not heartbeat Maria's session."""
        alex = _login(client, "alex.worker@amap.com")
        resp = client.post(
            "/api/v1/sessions/heartbeat",
            headers=_auth(alex),
            json={"work_session_id": maria_session},
        )
        assert resp.status_code == 200
        assert resp.json() is None  # foreign session -> not touched

        row = _pg(
            "SELECT last_heartbeat_at FROM work_sessions WHERE id = %s", (maria_session,)
        )
        assert row[0][0] is None, "foreign worker heartbeat must not refresh liveness"

    def test_supervisor_sees_last_action_from_execution_events(self, client):
        alex = _login(client, "alex.worker@amap.com")
        client.post(
            "/api/v1/actions/execute",
            headers=_auth(alex),
            json={"action_name": "select_item", "parameters": {"pointer_x": 10, "pointer_y": 10}},
        )
        sup = _login(client, "supervisor@amap.com")
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        alex_item = next(w for w in workers if w["worker_profile_id"] == ALEX)
        assert alex_item["last_action_description"] == "select_item"

    def test_pause_resume_updates_session_and_supervisor_status(self, client, maria_session):
        maria = _login(client, "maria.newhire@amap.com")
        sup = _login(client, "supervisor@amap.com")

        resp = client.post(f"/api/v1/sessions/{maria_session}/pause", headers=_auth(maria))
        assert resp.status_code == 200, resp.text
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria_item = next(w for w in workers if w["worker_profile_id"] == MARIA)
        assert maria_item["status"] == "PAUSED", maria_item

        resp = client.post(f"/api/v1/sessions/{maria_session}/resume", headers=_auth(maria))
        assert resp.status_code == 200, resp.text
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria_item = next(w for w in workers if w["worker_profile_id"] == MARIA)
        assert maria_item["status"] != "PAUSED"

    def test_end_session_shows_offline(self, client, maria_session):
        maria = _login(client, "maria.newhire@amap.com")
        resp = client.post(f"/api/v1/sessions/{maria_session}/end", headers=_auth(maria))
        assert resp.status_code == 200, resp.text
        sup = _login(client, "supervisor@amap.com")
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria_item = next(w for w in workers if w["worker_profile_id"] == MARIA)
        assert maria_item["is_online"] is False


# ---------------------------------------------------------------------------
# ASSIGNMENT EXECUTION: real workflow progression + persistence
# ---------------------------------------------------------------------------


@pytest.fixture()
def rt_workflow():
    """Dedicated 2-step workflow + task + assignment for Maria."""
    wf_id, task_id = str(uuid4()), str(uuid4())
    step_ids = [str(uuid4()) for _ in range(2)]
    assignment_id = str(uuid4())
    _pg(
        "INSERT INTO workflows (id, organization_id, name, description, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (wf_id, ORG, f"RT Workflow {uuid4().hex[:6]}", "RT fixture"),
    )
    for i, sid in enumerate(step_ids, start=1):
        _pg(
            "INSERT INTO workflow_steps (id, workflow_id, step_order, name, description, status) "
            "VALUES (%s, %s, %s, %s, %s, 'active')",
            (sid, wf_id, i, f"RT Step {i}", f"Realtime step {i}"),
        )
    _pg(
        "INSERT INTO tasks (id, organization_id, name, description, status) "
        "VALUES (%s, %s, %s, %s, 'active')",
        (task_id, ORG, f"RT Task {uuid4().hex[:6]}", "RT fixture"),
    )
    _pg("INSERT INTO task_workflows (task_id, workflow_id) VALUES (%s, %s)", (task_id, wf_id))
    _pg(
        "INSERT INTO worker_task_assignments (id, task_id, worker_profile_id, status) "
        "VALUES (%s, %s, %s, 'assigned')",
        (assignment_id, task_id, MARIA),
    )
    yield {"workflow_id": wf_id, "task_id": task_id, "step_ids": step_ids, "assignment_id": assignment_id}
    _pg(
        "DELETE FROM workflow_step_executions WHERE workflow_step_id = ANY(%s)",
        (step_ids,),
    )
    _pg(
        "DELETE FROM workflow_assignments WHERE workflow_id = %s AND worker_profile_id = %s",
        (wf_id, MARIA),
    )
    _pg("DELETE FROM task_results WHERE worker_task_assignment_id = %s", (assignment_id,))
    _pg("DELETE FROM worker_task_assignments WHERE id = %s", (assignment_id,))
    _pg("DELETE FROM task_workflows WHERE task_id = %s", (task_id,))
    _pg("DELETE FROM tasks WHERE id = %s", (task_id,))
    _pg("DELETE FROM workflow_steps WHERE workflow_id = %s", (wf_id,))
    _pg("DELETE FROM workflows WHERE id = %s", (wf_id,))


class TestAssignmentExecutionFlow:
    def test_full_gesture_task_flow_persists(self, client, rt_workflow):
        """start_assignment -> complete_step (x2) -> finish_assignment, with
        progress restorable afterwards (refresh/re-login persistence)."""
        maria = _login(client, "maria.newhire@amap.com")

        # 1. start assignment (voice "start task" resolves to start_assignment)
        resp = client.post(
            f"/api/v1/tasks/assignments/{rt_workflow['assignment_id']}/start",
            headers=_auth(maria),
        )
        assert resp.status_code == 200, resp.text
        wf_assignment_id = resp.json()["workflow_assignment_id"]
        assert wf_assignment_id

        # 2. complete step 1 (gesture complete_step)
        resp = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assignment_id}/steps/{rt_workflow['step_ids'][0]}/execute",
            headers=_auth(maria),
            json={"status": "completed", "execution_data": {"completed_via": "gesture"}},
        )
        assert resp.status_code == 201, resp.text

        # 3. progress restore endpoint returns completed steps (refresh)
        resp = client.get(
            f"/api/v1/tasks/workflows/assignments/{wf_assignment_id}/executions",
            headers=_auth(maria),
        )
        assert resp.status_code == 200, resp.text
        executions = resp.json()
        assert len(executions) == 1
        assert executions[0]["status"] == "completed"

        # 4. worker cannot read another worker's executions (tenant/ownership)
        alex = _login(client, "alex.worker@amap.com")
        resp = client.get(
            f"/api/v1/tasks/workflows/assignments/{wf_assignment_id}/executions",
            headers=_auth(alex),
        )
        assert resp.status_code == 403

        # 5. complete step 2 then finish
        resp = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assignment_id}/steps/{rt_workflow['step_ids'][1]}/execute",
            headers=_auth(maria),
            json={"status": "completed", "execution_data": {"completed_via": "gesture"}},
        )
        assert resp.status_code == 201, resp.text

        resp = client.post(
            f"/api/v1/tasks/assignments/{rt_workflow['assignment_id']}/complete",
            headers=_auth(maria),
            json={"outcome": "completed"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["result_data"]["completed_steps"] == 2
        assert body["result_data"]["total_steps"] == 2

        # 6. supervisor sees the completed assignment (real telemetry)
        sup = _login(client, "supervisor@amap.com")
        workers = client.get("/api/v1/supervisor/workers", headers=_auth(sup)).json()
        maria_item = next(w for w in workers if w["worker_profile_id"] == MARIA)
        # Maria has completed her fixture assignment; no other active assignment
        # from the seed, so she should not be stuck "WORKING" on it.
        assert maria_item["status"] != "WORKING" or maria_item["current_assignment_id"] != rt_workflow["assignment_id"]

    def test_step_order_enforced(self, client, rt_workflow):
        maria = _login(client, "maria.newhire@amap.com")
        resp = client.post(
            f"/api/v1/tasks/assignments/{rt_workflow['assignment_id']}/start",
            headers=_auth(maria),
        )
        wf_assignment_id = resp.json()["workflow_assignment_id"]

        # trying to complete step 2 before step 1 must fail
        resp = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assignment_id}/steps/{rt_workflow['step_ids'][1]}/execute",
            headers=_auth(maria),
            json={"status": "completed"},
        )
        assert resp.status_code == 409
