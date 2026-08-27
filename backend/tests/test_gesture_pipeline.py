"""
Tests for AMAP Gesture Input Pipeline (Phase 9).
Covers landmark classification heuristics, dwell-time state accumulation, and the gesture processing endpoint.
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.gesture import GestureFramePayload, LandmarkPoint
from services.gesture_service import GestureService


def _create_sample_hand(
    thumb_ext: bool = False,
    thumb_dir: str = "neutral",
    index_ext: bool = False,
    middle_ext: bool = False,
    ring_ext: bool = False,
    pinky_ext: bool = False,
    pinch: bool = False,
) -> list[LandmarkPoint]:
    """Helper to generate mock 21-landmark MediaPipe hand point sets."""
    landmarks = [LandmarkPoint(x=0.5, y=0.8, z=0.0)]  # 0: Wrist

    # 1-4: Thumb
    t_x = 0.30 if thumb_ext else 0.42
    t_y = (0.4 if thumb_dir == "up" else 0.95) if thumb_ext else 0.68
    if pinch:
        t_x, t_y = 0.5, 0.5
    landmarks.extend([
        LandmarkPoint(x=0.45, y=0.75, z=0.0),  # 1: CMC
        LandmarkPoint(x=0.40, y=0.70, z=0.0),  # 2: MCP
        LandmarkPoint(x=0.35, y=0.60, z=0.0),  # 3: IP
        LandmarkPoint(x=t_x, y=t_y, z=0.0),    # 4: Tip
    ])

    # 5-8: Index
    idx_tip_y = 0.4 if index_ext else 0.75
    if pinch:
        idx_tip_y = 0.5
    landmarks.extend([
        LandmarkPoint(x=0.48, y=0.65, z=0.0),  # 5: MCP
        LandmarkPoint(x=0.48, y=0.58, z=0.0),  # 6: PIP
        LandmarkPoint(x=0.48, y=0.50, z=0.0),  # 7: DIP
        LandmarkPoint(x=0.48 if not pinch else 0.5, y=idx_tip_y, z=0.0),  # 8: Tip
    ])

    # 9-12: Middle
    mid_tip_y = 0.38 if middle_ext else 0.76
    landmarks.extend([
        LandmarkPoint(x=0.52, y=0.65, z=0.0),  # 9: MCP
        LandmarkPoint(x=0.52, y=0.57, z=0.0),  # 10: PIP
        LandmarkPoint(x=0.52, y=0.48, z=0.0),  # 11: DIP
        LandmarkPoint(x=0.52, y=mid_tip_y, z=0.0),  # 12: Tip
    ])

    # 13-16: Ring
    ring_tip_y = 0.42 if ring_ext else 0.77
    landmarks.extend([
        LandmarkPoint(x=0.56, y=0.66, z=0.0),  # 13: MCP
        LandmarkPoint(x=0.56, y=0.59, z=0.0),  # 14: PIP
        LandmarkPoint(x=0.56, y=0.51, z=0.0),  # 15: DIP
        LandmarkPoint(x=0.56, y=ring_tip_y, z=0.0),  # 16: Tip
    ])

    # 17-20: Pinky
    pnk_tip_y = 0.45 if pinky_ext else 0.78
    landmarks.extend([
        LandmarkPoint(x=0.60, y=0.68, z=0.0),  # 17: MCP
        LandmarkPoint(x=0.60, y=0.62, z=0.0),  # 18: PIP
        LandmarkPoint(x=0.60, y=0.55, z=0.0),  # 19: DIP
        LandmarkPoint(x=0.60, y=pnk_tip_y, z=0.0),  # 20: Tip
    ])

    return landmarks


# =====================================================================
# Landmark Classification Tests
# =====================================================================

def test_classify_open_palm():
    service = GestureService()
    open_hand = _create_sample_hand(
        thumb_ext=True,
        index_ext=True,
        middle_ext=True,
        ring_ext=True,
        pinky_ext=True,
    )
    gesture, conf, *_ = service.classify_landmarks(open_hand)
    assert gesture == "open_palm"
    assert conf >= 0.90


def test_classify_fist():
    service = GestureService()
    fist_hand = _create_sample_hand(
        thumb_ext=False,
        index_ext=False,
        middle_ext=False,
        ring_ext=False,
        pinky_ext=False,
    )
    gesture, conf, *_ = service.classify_landmarks(fist_hand)
    assert gesture == "fist"
    assert conf >= 0.85


def test_classify_thumbs_up():
    service = GestureService()
    thumbs_up_hand = _create_sample_hand(
        thumb_ext=True,
        thumb_dir="up",
        index_ext=False,
        middle_ext=False,
        ring_ext=False,
        pinky_ext=False,
    )
    gesture, conf, *_ = service.classify_landmarks(thumbs_up_hand)
    assert gesture == "thumbs_up"
    assert conf >= 0.90


def test_classify_thumbs_down():
    service = GestureService()
    thumbs_down_hand = _create_sample_hand(
        thumb_ext=True,
        thumb_dir="down",
        index_ext=False,
        middle_ext=False,
        ring_ext=False,
        pinky_ext=False,
    )
    gesture, conf, *_ = service.classify_landmarks(thumbs_down_hand)
    assert gesture == "thumbs_down"
    assert conf >= 0.90


def test_classify_pointing():
    service = GestureService()
    point_hand = _create_sample_hand(
        thumb_ext=False,
        index_ext=True,
        middle_ext=False,
        ring_ext=False,
        pinky_ext=False,
    )
    gesture, conf, *_ = service.classify_landmarks(point_hand)
    assert gesture == "pointing"
    assert conf >= 0.90


def test_classify_pinch():
    service = GestureService()
    pinch_hand = _create_sample_hand(pinch=True)
    gesture, conf, *_ = service.classify_landmarks(pinch_hand)
    assert gesture == "pinch"
    assert conf >= 0.85


# =====================================================================
# Temporal Dwell-Time Accumulator Tests
# =====================================================================

def test_dwell_time_accumulation_and_trigger():
    service = GestureService()
    worker_id = uuid.uuid4()
    thumbs_up = _create_sample_hand(thumb_ext=True, thumb_dir="up")

    # Frame 1: 0ms -> dwell progress ~0%
    f1 = GestureFramePayload(
        landmarks=thumbs_up,
        timestamp_ms=1000,
        dwell_time_ms=500,
    )
    r1 = service.process_frame(f1, worker_profile_id=worker_id)
    assert r1.detected_gesture == "thumbs_up"
    assert r1.is_triggered is False
    assert r1.dwell_progress == 0.0

    # Frame 2: 250ms elapsed -> dwell progress ~50%
    f2 = GestureFramePayload(
        landmarks=thumbs_up,
        timestamp_ms=1250,
        dwell_time_ms=500,
    )
    r2 = service.process_frame(f2, worker_profile_id=worker_id)
    assert r2.detected_gesture == "thumbs_up"
    assert r2.is_triggered is False
    assert r2.dwell_progress == pytest.approx(0.5, rel=1e-2)

    # Frame 3: 500ms elapsed -> triggers!
    f3 = GestureFramePayload(
        landmarks=thumbs_up,
        timestamp_ms=1500,
        dwell_time_ms=500,
    )
    r3 = service.process_frame(f3, worker_profile_id=worker_id)
    assert r3.detected_gesture == "thumbs_up"
    assert r3.is_triggered is True
    assert r3.dwell_progress == 1.0
    assert r3.action_mapping == "confirm_action"

    # Frame 4: Continuous hold after trigger -> stays at 1.0, is_triggered False
    f4 = GestureFramePayload(
        landmarks=thumbs_up,
        timestamp_ms=1600,
        dwell_time_ms=500,
    )
    r4 = service.process_frame(f4, worker_profile_id=worker_id)
    assert r4.is_triggered is False
    assert r4.dwell_progress == 1.0


# =====================================================================
# Gesture Frame API Route Tests
# =====================================================================

def test_gesture_frame_api_endpoint():
    client = TestClient(app)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    mock_user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=worker_id,
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        open_hand = _create_sample_hand(
            thumb_ext=True,
            index_ext=True,
            middle_ext=True,
            ring_ext=True,
            pinky_ext=True,
        )

        resp = client.post(
            "/api/v1/gestures/process-frame",
            json={
                "landmarks": [p.model_dump() for p in open_hand],
                "handedness": "Right",
                "timestamp_ms": 2000,
                "dwell_time_ms": 300,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected_gesture"] == "open_palm"
        assert data["action_mapping"] == "pause_session"

    finally:
        app.dependency_overrides.clear()
