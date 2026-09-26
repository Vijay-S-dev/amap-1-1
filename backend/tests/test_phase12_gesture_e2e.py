"""Phase 12: gesture pipeline end-to-end tests (HTTP -> service -> PostgreSQL).

Covers:
- camera-frame landmarks -> POST /gestures/process-frame -> dwell trigger ->
  audit_events row in PostgreSQL
- custom gesture train -> custom_gestures row in PostgreSQL -> live frame
  classified as custom -> trigger audited -> delete -> row gone
- authentication and validation error paths (no silent failures)
"""

from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.test_gesture_pipeline import _create_sample_hand
from tests.test_custom_gestures import generate_mock_landmarks_with_pose

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
DEFAULT_PASSWORD = "SecurePassword123!"


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


def _payload(hand, ts, handedness="Right", dwell=500):
    return {
        "landmarks": [
            {"x": p.x, "y": p.y, "z": getattr(p, "z", 0.0)} for p in hand
        ],
        "handedness": handedness,
        "timestamp_ms": ts,
        "dwell_time_ms": dwell,
    }


def test_process_frame_trigger_writes_audit_event(client):
    """Real HTTP frame processing fires and lands in audit_events."""
    token = _login(client, "alex.worker@amap.com")
    hand = _create_sample_hand(thumb_ext=True, thumb_dir="up")

    before = _pg("SELECT COUNT(*) FROM audit_events WHERE event_type = 'gesture.recognized'")[0][0]

    # Dwell accumulation across frames until trigger
    results = []
    for i in range(6):
        resp = client.post(
            "/api/v1/gestures/process-frame",
            json=_payload(hand, ts=1_000_000 + i * 400),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        results.append(resp.json())

    assert results[0]["detected_gesture"] == "thumbs_up"
    assert results[0]["is_triggered"] is False
    assert results[0]["dwell_progress"] == 0.0
    # one-shot latch: the dwell fires exactly once during the hold
    fired = [r for r in results if r["is_triggered"]]
    assert fired, "dwell must trigger within the hold window"
    assert fired[0]["dwell_progress"] == 1.0
    assert fired[0]["action_mapping"], "trigger must map to an action"
    assert sum(1 for r in results if r["is_triggered"]) == 1

    after = _pg(
        "SELECT event_data, actor_user_id FROM audit_events "
        "WHERE event_type = 'gesture.recognized' ORDER BY created_at DESC LIMIT 1"
    )
    assert after, "gesture trigger must be audited to PostgreSQL"
    assert after[0][0]["gesture"] == "thumbs_up"
    count_after = _pg(
        "SELECT COUNT(*) FROM audit_events WHERE event_type = 'gesture.recognized'"
    )[0][0]
    assert count_after > before

    # cleanup audit rows created by this test (keep table tidy for other tests)
    _pg("DELETE FROM audit_events WHERE event_type = 'gesture.recognized'")


def test_custom_gesture_train_classify_delete_persistence(client):
    """Custom gesture: HTTP train -> PG row -> live custom classification ->
    audited trigger -> delete -> PG row removed from active list."""
    token = _login(client, "alex.worker@amap.com")
    uid = _pg(
        "SELECT id FROM worker_profiles WHERE user_id = "
        "(SELECT id FROM users WHERE email='alex.worker@amap.com')"
    )[0][0]
    marker = f"Phase12 Wave {uuid4().hex[:8]}"

    # ensure clean slate for this worker
    existing = client.get("/api/v1/gestures/custom", headers=_auth(token)).json()
    for g in existing:
        if g["gesture_name"] == marker:
            client.delete(f"/api/v1/gestures/custom/{g['id']}", headers=_auth(token))

    samples = [
        [
            {"x": p.x, "y": p.y, "z": getattr(p, "z", 0.0)}
            for p in generate_mock_landmarks_with_pose(index_tip_y=0.22, jitter=i * 0.002)
        ]
        for i in range(5)
    ]

    # invalid sample count -> 422 (no silent acceptance)
    resp = client.post(
        "/api/v1/gestures/custom/train",
        json={
            "gesture_name": "Bad Gesture",
            "intent": "CONFIRM",
            "samples": samples[:3],
            "handedness": "Right",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text

    # train
    resp = client.post(
        "/api/v1/gestures/custom/train",
        json={
            "gesture_name": marker,
            "intent": "CONFIRM",
            "samples": samples,
            "handedness": "Right",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    gesture_id = resp.json()["id"]

    # PostgreSQL row exists with the owning worker
    row = _pg(
        "SELECT worker_id, gesture_name, intent, sample_count, status "
        "FROM custom_gestures WHERE gesture_name = %s",
        (marker,),
    )
    assert row, "custom gesture must be persisted to PostgreSQL"
    assert row[0][0] == uid and row[0][2] == "CONFIRM" and row[0][3] == 5
    assert row[0][4] == "active"

    # refresh-persistence: a fresh GET (new request) sees it
    listed = client.get("/api/v1/gestures/custom", headers=_auth(token)).json()
    assert any(g["gesture_name"] == marker for g in listed)

    # live frame -> server classifies as THIS custom gesture
    live_hand = generate_mock_landmarks_with_pose(index_tip_y=0.22)
    results = []
    for i in range(6):
        resp = client.post(
            "/api/v1/gestures/process-frame",
            json=_payload(live_hand, ts=2_000_000 + i * 400),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        results.append(resp.json())
    fired = [r for r in results if r["is_triggered"]]
    assert fired, "custom gesture dwell must trigger"
    triggered = fired[0]
    assert triggered["is_custom"] is True
    assert triggered["custom_gesture_id"] == gesture_id
    assert triggered["detected_gesture"] == "custom_confirm"
    assert triggered["is_triggered"] is True
    assert triggered["action_mapping"] == "confirm_action"

    # audited trigger row carries custom identity
    audited = _pg(
        "SELECT event_data FROM audit_events WHERE event_type = 'gesture.recognized' "
        "ORDER BY created_at DESC LIMIT 1"
    )
    assert audited and audited[0][0]["is_custom"] is True
    assert audited[0][0]["custom_gesture_id"] == gesture_id

    # delete -> gone from list and status flipped in PG
    resp = client.delete(f"/api/v1/gestures/custom/{gesture_id}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    listed = client.get("/api/v1/gestures/custom", headers=_auth(token)).json()
    assert not any(g["gesture_name"] == marker for g in listed)
    row = _pg(
        "SELECT status FROM custom_gestures WHERE id = %s",
        (gesture_id,),
    )
    assert row and row[0][0] in ("deleted", "replaced"), row

    # delete again -> 404 (no silent success)
    resp = client.delete(f"/api/v1/gestures/custom/{gesture_id}", headers=_auth(token))
    assert resp.status_code == 404, resp.text

    # cleanup audit rows from this test
    _pg("DELETE FROM audit_events WHERE event_type = 'gesture.recognized'")
    _pg("DELETE FROM custom_gestures WHERE gesture_name = %s", (marker,))


def test_gesture_endpoints_require_authentication(client):
    hand = _create_sample_hand(thumb_ext=True, thumb_dir="up")
    resp = client.post(
        "/api/v1/gestures/process-frame", json=_payload(hand, ts=1)
    )
    assert resp.status_code in (401, 403), resp.text
    resp = client.get("/api/v1/gestures/custom")
    assert resp.status_code in (401, 403), resp.text
    resp = client.post(
        "/api/v1/gestures/custom/train",
        json={"gesture_name": "x", "intent": "CONFIRM", "samples": []},
    )
    assert resp.status_code in (401, 403), resp.text
