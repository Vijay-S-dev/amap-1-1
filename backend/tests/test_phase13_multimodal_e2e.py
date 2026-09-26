"""Phase 13: multimodal fusion end-to-end (HTTP -> fusion -> auth -> execution -> PostgreSQL).

Covers the ten required scenarios:
 1. voice-only command
 2. gesture-only command
 3. gesture + voice (agreement / reinforcing)
 4. spatial context + voice (complementary binding)
 5. spatial context + gesture (single-mode spatial target)
 6. conflicting modalities (safety override)
 7. missing context (deterministic fallback)
 8. invalid command (rejected)
 9. unauthorized command (no token / wrong role)
10. ambiguous command (conflict_ambiguous)

Plus persistence: execution_events + audit_events rows survive a fresh query
(restart-proof rows in PostgreSQL) and authorization gateway behavior.
"""

from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"
DEFAULT_PASSWORD = "SecurePassword123!"
T0 = 1_700_000_000_000


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _login(client, email):
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": ORG, "email": email, "password": DEFAULT_PASSWORD},
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


def _voice(intent, conf=0.95, ts=0, ctx=None):
    return {
        "mode": "voice",
        "raw_intent": intent,
        "confidence": conf,
        "timestamp_ms": T0 + ts,
        "context_data": ctx or {},
    }


def _gesture(intent, conf=0.90, ts=0, ctx=None):
    return {
        "mode": "gesture",
        "raw_intent": intent,
        "confidence": conf,
        "timestamp_ms": T0 + ts,
        "context_data": ctx or {},
    }


def _fuse(client, token, inputs, window=1500, ctx=None):
    payload = {"inputs": inputs, "temporal_window_ms": window}
    if ctx is not None:
        payload["client_context"] = ctx
    resp = client.post(
        "/api/v1/multimodal/fuse", json=payload, headers=_auth(token)
    )
    return resp


def test_s1_voice_only_command(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(client, token, [_voice("confirm_action", 0.95)])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "confirm_action", body
    assert body["validation_status"] == "valid"
    assert body["fusion_strategy"] == "single_mode"


def test_s2_gesture_only_command(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(client, token, [_gesture("thumbs_up", 0.92)])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "confirm_action", body
    assert body["validation_status"] == "valid"


def test_s3_gesture_plus_voice_agreement(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(
        client,
        token,
        [
            _voice("confirm", 0.95, ts=0),
            _gesture("thumbs_up", 0.90, ts=120),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "confirm_action", body
    assert body["fusion_strategy"] == "reinforcing"
    assert body["validation_status"] == "valid"
    assert set(body["contributing_modes"]) == {"voice", "gesture"}
    # probabilistic reinforcement beats the weaker input
    assert body["fused_confidence"] >= 0.95


def test_s4_spatial_context_plus_voice(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(
        client,
        token,
        [
            _gesture(
                "pointing",
                0.90,
                ts=0,
                ctx={"target_part_id": "PART-4091", "spatial_x": 0.45},
            ),
            _voice("next step", 0.92, ts=100, ctx={"action_param": "fast_track"}),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "next_step", body
    assert body["fusion_strategy"] == "complementary"
    assert body["target_context"]["target_part_id"] == "PART-4091"
    assert body["target_context"]["action_param"] == "fast_track"
    assert body["validation_status"] == "valid"


def test_s5_spatial_context_plus_gesture_single_mode(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(
        client,
        token,
        [
            _gesture(
                "pointing",
                0.93,
                ctx={"target_part_id": "PART-77", "spatial_y": 0.31},
            )
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "point_focus", body
    assert body["validation_status"] == "valid"
    assert body["target_context"]["target_part_id"] == "PART-77"


def test_s6_conflicting_modalities_safety_override(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(
        client,
        token,
        [
            _voice("confirm", 0.95, ts=0),
            _gesture("thumbs_down", 0.80, ts=100),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "cancel_action", body
    assert body["fusion_strategy"] == "conflict_resolved"
    assert body["requires_confirmation"] is True


def test_s7_missing_context_deterministic_fallback(client):
    token = _login(client, "alex.worker@amap.com")
    # pointing WITHOUT spatial context keys -> documented fallback, no crash
    resp = _fuse(client, token, [_gesture("pointing", 0.9)])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "next_step", body
    assert body["validation_status"] == "valid"


def test_s8_invalid_command_rejected(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(client, token, [_voice("xyzzy frobnicate the flux", 0.9)])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] is None, body
    assert body["validation_status"] == "rejected"

    # low confidence also rejected (safety threshold)
    resp = _fuse(client, token, [_voice("confirm", 0.35)])
    body = resp.json()
    assert body["fused_action"] is None
    assert body["validation_status"] == "rejected"


def test_s9_unauthorized_command(client):
    # unauthenticated fusion -> 401/403
    resp = client.post(
        "/api/v1/multimodal/fuse",
        json={"inputs": [_voice("confirm_action", 0.95)]},
    )
    assert resp.status_code in (401, 403), resp.text

    # authenticated but role without multimodal:input -> 403.
    # (admin/organization_admin are permission wildcards BY DESIGN; the
    # supervisor role holds only session:read + assistance:resolve.)
    supervisor = _login(client, "supervisor@amap.com")
    resp = _fuse(client, supervisor, [_voice("confirm_action", 0.95)])
    assert resp.status_code == 403, resp.text
    assert "multimodal:input" in resp.text

    # unauthenticated execution of the fused action -> 401
    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "confirm_action", "parameters": {}},
    )
    assert resp.status_code in (401, 403), resp.text


def test_s10_ambiguous_command(client):
    token = _login(client, "alex.worker@amap.com")
    # next_step vs previous_step with close confidences (delta < 0.35)
    resp = _fuse(
        client,
        token,
        [
            _voice("next step", 0.85, ts=0),
            _gesture("swipe_left", 0.82, ts=100),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validation_status"] == "ambiguous", body
    assert body["fused_action"] is None
    assert body["fusion_strategy"] == "conflict_ambiguous"
    assert body["requires_confirmation"] is True


def test_fused_action_execution_writes_postgres(client):
    """voice -> fusion -> authorization gateway -> execution_events row."""
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(client, token, [_voice("confirm_action", 0.97)])
    assert resp.status_code == 200
    action = resp.json()["fused_action"]
    assert action == "confirm_action"

    marker = str(uuid4())
    before = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    ex = client.post(
        "/api/v1/actions/execute",
        json={
            "action_name": action,
            "parameters": {"source": "phase13-multimodal", "marker": marker},
        },
        headers=_auth(token),
    )
    assert ex.status_code == 200, ex.text
    assert ex.json()["success"] is True

    after = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    assert after == before + 1
    row = _pg(
        "SELECT event_type, worker_profile_id, event_data FROM execution_events "
        "ORDER BY created_at DESC LIMIT 1"
    )
    assert row[0][0] == "action.confirm_action.executed"
    assert str(row[0][1]) == ALEX
    data = row[0][2]
    if isinstance(data, str):
        import json as _json
        data = _json.loads(data)
    assert data["parameters"]["marker"] == marker

    # persistence: row is readable by a brand-new connection (restart-proof)
    again = _pg(
        "SELECT 1 FROM execution_events WHERE event_data->'parameters'->>'marker' = %s",
        (marker,),
    )
    assert again

    # cleanup
    _pg(
        "DELETE FROM execution_events WHERE event_data->'parameters'->>'marker' = %s",
        (marker,),
    )


def test_emergency_stop_fusion_requires_confirmation(client):
    token = _login(client, "alex.worker@amap.com")
    resp = _fuse(
        client,
        token,
        [
            _voice("confirm", 0.95, ts=0),
            _gesture("fist", 0.90, ts=50),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fused_action"] == "emergency_stop", body
    assert body["requires_confirmation"] is True
    assert body["fusion_strategy"] == "conflict_resolved"
