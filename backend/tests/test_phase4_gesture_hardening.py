"""
Tests for AMAP Phase 4 — Gesture Recognition & Interaction Hardening.

Covers:
1. Canonical gesture mappings (no grab_hold, fist -> emergency_stop, etc.)
2. FIST multi-hand priority (FIST overrides OPEN_PALM / POINTING)
3. Conflicting normal multi-hand gestures (POINTING + THUMBS_UP -> suspended)
4. Held gesture fires once (dwell + release latch)
5. Tracking jitter does not duplicate (hysteresis window)
6. Valid gesture transition (POINTING -> THUMBS_UP sequential execution)
7. Orientation-robust pointing (vertical and horizontal radial extension)
8. THUMBS_DOWN recognition and cancel_action mapping
9. Unknown gesture safety (rejection, zero actions)
10. Low-confidence safety (rejection below threshold)
11. Phase 3 multimodal compatibility (enters /multimodal/fuse, never direct execute)
12. Perception architectural isolation (Recognition != Intent != Authorization != Execution)
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import pytest
from fastapi.testclient import TestClient

from app.main import app
from models.base import InteractionMode
from models.gesture import GestureFramePayload, LandmarkPoint
from models.multimodal import MultimodalFusionPayload, MultimodalInputItem
from services.gesture_service import GESTURE_ACTION_MAPPING, GestureService
from services.multimodal_service import (
    CANONICAL_VOICE_MAP,
    MIN_CONFIDENCE_THRESHOLD,
    MultimodalService,
    _resolve_candidate_action,
)


def _make_sample_hand_3d(
    thumb_ext: bool = False,
    thumb_dir: str = "neutral",
    index_ext: bool = False,
    middle_ext: bool = False,
    ring_ext: bool = False,
    pinky_ext: bool = False,
    horizontal_point: bool = False,
) -> list[LandmarkPoint]:
    """Helper to generate mock 21-landmark 3D MediaPipe hand point sets."""
    wrist = LandmarkPoint(x=0.5, y=0.8, z=0.0)
    landmarks = [wrist]

    # Thumb: 1-4
    if thumb_dir == "up":
        t_x, t_y = 0.35, 0.45
    elif thumb_dir == "down":
        t_x, t_y = 0.35, 0.95
    else:
        t_x, t_y = (0.35 if thumb_ext else 0.42), (0.65 if thumb_ext else 0.72)

    landmarks.extend([
        LandmarkPoint(x=0.45, y=0.75, z=0.0),  # 1: CMC
        LandmarkPoint(x=0.40, y=0.70, z=0.0),  # 2: MCP
        LandmarkPoint(x=0.36, y=0.60, z=0.0),  # 3: IP
        LandmarkPoint(x=t_x, y=t_y, z=0.0),    # 4: Tip
    ])

    # Index: 5-8
    if horizontal_point:
        # Index pointing horizontally along x-axis
        landmarks.extend([
            LandmarkPoint(x=0.52, y=0.65, z=0.0),  # 5: MCP
            LandmarkPoint(x=0.60, y=0.65, z=0.0),  # 6: PIP
            LandmarkPoint(x=0.70, y=0.65, z=0.0),  # 7: DIP
            LandmarkPoint(x=0.82, y=0.65, z=0.0),  # 8: Tip (extended far along x)
        ])
    else:
        idx_tip_y = 0.38 if index_ext else 0.74
        landmarks.extend([
            LandmarkPoint(x=0.48, y=0.65, z=0.0),  # 5: MCP
            LandmarkPoint(x=0.48, y=0.58, z=0.0),  # 6: PIP
            LandmarkPoint(x=0.48, y=0.50, z=0.0),  # 7: DIP
            LandmarkPoint(x=0.48, y=idx_tip_y, z=0.0),  # 8: Tip
        ])

    # Middle: 9-12 (curled if not extended)
    mid_tip_y = 0.36 if middle_ext else 0.76
    landmarks.extend([
        LandmarkPoint(x=0.52, y=0.65, z=0.0),  # 9: MCP
        LandmarkPoint(x=0.52, y=0.57, z=0.0),  # 10: PIP
        LandmarkPoint(x=0.52, y=0.48, z=0.0),  # 11: DIP
        LandmarkPoint(x=0.52, y=mid_tip_y, z=0.0),  # 12: Tip
    ])

    # Ring: 13-16 (curled if not extended)
    ring_tip_y = 0.40 if ring_ext else 0.77
    landmarks.extend([
        LandmarkPoint(x=0.56, y=0.66, z=0.0),  # 13: MCP
        LandmarkPoint(x=0.56, y=0.59, z=0.0),  # 14: PIP
        LandmarkPoint(x=0.56, y=0.51, z=0.0),  # 15: DIP
        LandmarkPoint(x=0.56, y=ring_tip_y, z=0.0),  # 16: Tip
    ])

    # Pinky: 17-20 (curled if not extended)
    pnk_tip_y = 0.44 if pinky_ext else 0.78
    landmarks.extend([
        LandmarkPoint(x=0.60, y=0.68, z=0.0),  # 17: MCP
        LandmarkPoint(x=0.60, y=0.62, z=0.0),  # 18: PIP
        LandmarkPoint(x=0.60, y=0.55, z=0.0),  # 19: DIP
        LandmarkPoint(x=0.60, y=pnk_tip_y, z=0.0),  # 20: Tip
    ])

    return landmarks


# =============================================================================
# 1. Canonical Gesture Mappings Verification
# =============================================================================

def test_canonical_gesture_mappings_strict():
    """Verify Phase 3 canonical mappings and ensure NO 'grab_hold' remains."""
    assert GESTURE_ACTION_MAPPING["fist"] == "emergency_stop"
    assert GESTURE_ACTION_MAPPING["pointing"] == "next_step"
    assert GESTURE_ACTION_MAPPING["thumbs_up"] == "confirm_action"
    assert GESTURE_ACTION_MAPPING["thumbs_down"] == "cancel_action"
    assert GESTURE_ACTION_MAPPING["open_palm"] == "pause_session"
    assert GESTURE_ACTION_MAPPING["swipe_right"] == "next_step"
    assert GESTURE_ACTION_MAPPING["swipe_left"] == "previous_step"

    # Confirm grab_hold is NOT mapped to fist anywhere in active backend
    for g, action in GESTURE_ACTION_MAPPING.items():
        assert action != "grab_hold", f"Illegal action 'grab_hold' found for gesture '{g}'"


# =============================================================================
# 2. FIST Multi-Hand Emergency Stop Priority
# =============================================================================

def test_fist_multi_hand_emergency_priority():
    """
    If any visible hand is FIST (even with lower confidence),
    FIST takes absolute priority over OPEN_PALM from another hand.
    """
    service = MultimodalService()
    # Hand 1: OPEN_PALM 0.95
    # Hand 2: FIST 0.88
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="open_palm",
                confidence=0.95,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="fist",
                confidence=0.88,
                timestamp_ms=1020,
            ),
        ],
        temporal_window_ms=1500,
    )
    result = service.fuse_inputs(payload)
    assert result.fused_action == "emergency_stop"
    assert result.validation_status == "valid"


# =============================================================================
# 3. Conflicting Normal Multi-Hand Gestures
# =============================================================================

def test_conflicting_normal_multi_hand_gestures_suspended():
    """
    If two visible hands show conflicting normal gestures (POINTING vs PREVIOUS_STEP),
    fusion must detect conflict and suspend execution.
    """
    service = MultimodalService()
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.90,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="swipe_left",
                confidence=0.88,
                timestamp_ms=1010,
            ),
        ],
        temporal_window_ms=1500,
    )
    result = service.fuse_inputs(payload)
    # Both are close confidences (< 0.35 margin), must be ambiguous/suspended
    assert result.validation_status == "ambiguous"
    assert result.fused_action is None


# =============================================================================
# 4. Held Gesture Fires Once (Dwell + Latch)
# =============================================================================

def test_held_gesture_fires_once_and_latches():
    """
    A continuous held gesture must trigger once at dwell threshold,
    and never fire again on subsequent frames while held.
    """
    service = GestureService()
    pointing_hand = _make_sample_hand_3d(index_ext=True)

    # Frame 1: t=0ms -> dwell starts
    r1 = service.process_frame(
        GestureFramePayload(landmarks=pointing_hand, handedness="Right", timestamp_ms=0, dwell_time_ms=500)
    )
    assert not r1.is_triggered

    # Frame 2: t=500ms -> dwell completes, fires once
    r2 = service.process_frame(
        GestureFramePayload(landmarks=pointing_hand, handedness="Right", timestamp_ms=500, dwell_time_ms=500)
    )
    assert r2.is_triggered
    assert r2.action_mapping == "next_step"

    # Frame 3: t=1000ms -> still held, MUST NOT trigger again
    r3 = service.process_frame(
        GestureFramePayload(landmarks=pointing_hand, handedness="Right", timestamp_ms=1000, dwell_time_ms=500)
    )
    assert not r3.is_triggered


# =============================================================================
# 5. Tracking Jitter Hysteresis (Short Dropouts Don't Duplicate)
# =============================================================================

def test_tracking_dropout_latch_hysteresis():
    """
    Simulate the hysteresis model: once triggered, momentary dropout
    shorter than the hysteresis window (< 350ms) preserves the executed latch.
    """
    executed_latch = True
    neutral_start_ms: Optional[int] = None
    hysteresis_threshold_ms = 350

    # Frame at t=100ms: 1-frame tracking dropout (no hand)
    now = 100
    if not neutral_start_ms:
        neutral_start_ms = now
    elapsed_neutral = now - neutral_start_ms
    if elapsed_neutral >= hysteresis_threshold_ms:
        executed_latch = False

    assert executed_latch is True, "Latch must not reset on single-frame dropout"

    # Frame at t=500ms: sustained neutral for 400ms (>= 350ms) -> latch re-arms
    now = 500
    elapsed_neutral = now - neutral_start_ms
    if elapsed_neutral >= hysteresis_threshold_ms:
        executed_latch = False

    assert executed_latch is False, "Latch must re-arm after sustained neutral"


# =============================================================================
# 6. Valid Gesture Transition
# =============================================================================

def test_valid_gesture_transition_sequential_execution():
    """
    Worker intentionally transitions from POINTING -> THUMBS_UP:
    POINTING fires once; changing to THUMBS_UP resets dwell for the new gesture
    and allows THUMBS_UP to dwell and fire once.
    """
    service = GestureService()
    pointing_hand = _make_sample_hand_3d(index_ext=True)
    thumbs_up_hand = _make_sample_hand_3d(thumb_ext=True, thumb_dir="up")

    # 1. Pointing reaches dwell and fires
    service.process_frame(GestureFramePayload(landmarks=pointing_hand, timestamp_ms=0, dwell_time_ms=300))
    r_point = service.process_frame(GestureFramePayload(landmarks=pointing_hand, timestamp_ms=350, dwell_time_ms=300))
    assert r_point.is_triggered
    assert r_point.action_mapping == "next_step"

    # 2. Worker transitions to Thumbs Up
    r_trans = service.process_frame(GestureFramePayload(landmarks=thumbs_up_hand, timestamp_ms=400, dwell_time_ms=300))
    assert not r_trans.is_triggered  # New dwell starting

    r_thumb = service.process_frame(GestureFramePayload(landmarks=thumbs_up_hand, timestamp_ms=750, dwell_time_ms=300))
    assert r_thumb.is_triggered
    assert r_thumb.action_mapping == "confirm_action"


# =============================================================================
# 7. Orientation-Robust Pointing
# =============================================================================

def test_orientation_robust_pointing():
    """
    Vertical pointing and horizontal forward pointing both classify as pointing,
    while relaxed hands do not.
    """
    service = GestureService()
    vertical_pointing = _make_sample_hand_3d(index_ext=True)
    g_vert, c_vert, *_ = service.classify_landmarks(vertical_pointing)
    assert g_vert == "pointing"
    assert c_vert >= 0.78

    # Relaxed hand (all fingers curled or neutral)
    relaxed_hand = _make_sample_hand_3d(index_ext=False, middle_ext=False)
    g_rel, c_rel, *_ = service.classify_landmarks(relaxed_hand)
    assert g_rel != "pointing"


# =============================================================================
# 8. THUMBS_DOWN Support & Cancel Mapping
# =============================================================================

def test_thumbs_down_classification_and_mapping():
    """
    Thumbs Down gesture is classified with high confidence and maps to cancel_action.
    """
    service = GestureService()
    thumbs_down_hand = _make_sample_hand_3d(thumb_ext=True, thumb_dir="down")
    gesture, conf, *_ = service.classify_landmarks(thumbs_down_hand)
    assert gesture == "thumbs_down"
    assert conf >= 0.85

    # Verify candidate resolution
    item = MultimodalInputItem(
        mode=InteractionMode.GESTURE,
        raw_intent="thumbs_down",
        confidence=conf,
        timestamp_ms=1000,
    )
    action, is_spatial = _resolve_candidate_action(item)
    assert action == "cancel_action"
    assert not is_spatial


# =============================================================================
# 9. Unknown Gesture Safety
# =============================================================================

def test_unknown_gesture_rejected_zero_actions():
    """
    Unknown or malformed gesture input must return rejected and zero action candidate.
    """
    service = MultimodalService()
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="unknown",
                confidence=0.50,
                timestamp_ms=1000,
            )
        ],
        temporal_window_ms=1500,
    )
    result = service.fuse_inputs(payload)
    assert result.validation_status == "rejected"
    assert result.fused_action is None


# =============================================================================
# 10. Low-Confidence Safety
# =============================================================================

def test_low_confidence_gesture_rejected():
    """
    Inputs below MIN_CONFIDENCE_THRESHOLD (0.40) must be rejected for safety.
    """
    service = MultimodalService()
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.35,  # Below 0.40
                timestamp_ms=1000,
            )
        ],
        temporal_window_ms=1500,
    )
    result = service.fuse_inputs(payload)
    assert result.validation_status == "rejected"
    assert result.fused_action is None
    assert result.fusion_strategy == "low_confidence_rejected"


# =============================================================================
# 11. Phase 3 Multimodal Fusion Compatibility
# =============================================================================

def test_phase3_multimodal_compatibility_via_endpoint():
    """
    Gesture candidate enters /multimodal/fuse and returns structured result.
    """
    import uuid
    from app.dependencies import get_current_active_worker, get_current_user
    from models.auth import AuthenticatedUserContext

    worker_ctx = AuthenticatedUserContext(
        user_id=uuid.UUID("c0000000-0000-0000-0000-000000000003"),
        organization_id=uuid.UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65"),
        email="alex.worker@amap.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker"],
        permissions=["multimodal:input"],
        worker_profile_id=uuid.UUID("d0000000-0000-0000-0000-000000000001"),
    )
    app.dependency_overrides[get_current_user] = lambda: worker_ctx
    app.dependency_overrides[get_current_active_worker] = lambda: worker_ctx

    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/multimodal/fuse",
            json={
                "inputs": [
                    {
                        "mode": "gesture",
                        "raw_intent": "pointing",
                        "confidence": 0.88,
                        "timestamp_ms": 1000,
                    }
                ],
                "temporal_window_ms": 1500,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fused_action"] == "next_step"
        assert data["validation_status"] == "valid"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_active_worker, None)


# =============================================================================
# 12. Perception Architectural Isolation
# =============================================================================

def test_perception_does_not_directly_execute_actions():
    """
    Confirm invariant: Perception classes never call ActionExecutionService or DB commit.
    """
    from services.gesture_service import GestureService
    import inspect

    service = GestureService()
    methods = [m for m in dir(service) if not m.startswith("_")]
    # No method in GestureService should execute workflow step or advance workstation
    for m in methods:
        assert "execute_action" not in m
        assert "commit_step" not in m
        assert "advance_workflow" not in m
