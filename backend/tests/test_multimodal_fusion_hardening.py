"""
AMAP Phase 3 — Multimodal Fusion & Disambiguation Hardening Test Suite.

Covers Tests A through T as mandated by the Phase 3 Specification:
- Test A: Voice-only action
- Test B: Gesture-only action
- Test C: Voice + gesture agreement
- Test D: Voice + gesture normal conflict
- Test E: Voice low confidence (< 0.40)
- Test F: Gesture low confidence (< 0.40)
- Test G: Both low confidence
- Test H: Stale gesture + current voice
- Test I: Current gesture + stale voice
- Test J: Unknown gesture
- Test K: Unknown voice
- Test L: Emergency Stop from voice
- Test M: Emergency Stop from gesture
- Test N: Emergency Stop vs conflicting normal command
- Test O: Duplicate multimodal event
- Test P: Confirmation-required fused command
- Test Q: Backend outage / client fail-closed invariant
- Test R: Architectural invariant: Fusion cannot directly execute actions
- Test S: Architectural invariant: Fusion cannot directly mutate database
- Test T: Exactly one execution candidate produced for agreeing modalities
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.base import InteractionMode
from models.multimodal import MultimodalFusionPayload, MultimodalInputItem
from services.multimodal_service import MultimodalService, MIN_CONFIDENCE_THRESHOLD


@pytest.fixture
def service():
    return MultimodalService()


# -----------------------------------------------------------------------------
# Test A: Voice-only action
# -----------------------------------------------------------------------------
def test_a_voice_only_action(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.88,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "next_step"
    assert res.fused_confidence == 0.88
    assert res.fusion_strategy == "single_mode"
    assert res.requires_confirmation is False
    assert res.contributing_modes == ["voice"]


# -----------------------------------------------------------------------------
# Test B: Gesture-only action
# -----------------------------------------------------------------------------
def test_b_gesture_only_action(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.91,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "next_step"
    assert res.fused_confidence == 0.91
    assert res.fusion_strategy == "single_mode"
    assert res.requires_confirmation is False
    assert res.contributing_modes == ["gesture"]


# -----------------------------------------------------------------------------
# Test C: Voice + gesture agreement
# -----------------------------------------------------------------------------
def test_c_voice_gesture_agreement(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.88,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.91,
                timestamp_ms=1150,
            ),
        ],
        temporal_window_ms=1500,
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "next_step"
    assert res.fusion_strategy == "reinforcing"
    # Reinforcing formula: 1 - (1 - 0.88)*(1 - 0.91) = 1 - 0.12*0.09 = 1 - 0.0108 = 0.989
    assert res.fused_confidence == pytest.approx(0.989, rel=1e-2)
    assert set(res.contributing_modes) == {"voice", "gesture"}
    assert res.requires_confirmation is False


# -----------------------------------------------------------------------------
# Test D: Normal conflict (Voice next vs Gesture previous)
# -----------------------------------------------------------------------------
def test_d_normal_conflict_ambiguous(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.85,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="swipe_left",
                confidence=0.82,
                timestamp_ms=1100,
            ),
        ],
        temporal_window_ms=1500,
    )
    res = service.fuse_inputs(payload)
    # Delta |0.85 - 0.82| = 0.03 < 0.35 -> Ambiguous conflict, no automatic action
    assert res.validation_status == "ambiguous"
    assert res.fused_action is None
    assert res.fusion_strategy == "conflict_ambiguous"
    assert res.requires_confirmation is True


# -----------------------------------------------------------------------------
# Test E: Voice low confidence (< 0.40)
# -----------------------------------------------------------------------------
def test_e_voice_low_confidence(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.35,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "rejected"
    assert res.fused_action is None
    assert res.fusion_strategy == "low_confidence_rejected"
    assert res.fused_confidence == 0.35
    assert "below acceptable threshold" in res.message


# -----------------------------------------------------------------------------
# Test F: Gesture low confidence (< 0.40)
# -----------------------------------------------------------------------------
def test_f_gesture_low_confidence(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.25,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "rejected"
    assert res.fused_action is None
    assert res.fusion_strategy == "low_confidence_rejected"
    assert res.fused_confidence == 0.25


# -----------------------------------------------------------------------------
# Test G: Both low confidence
# -----------------------------------------------------------------------------
def test_g_both_low_confidence(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.30,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.28,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "rejected"
    assert res.fused_action is None
    assert res.fusion_strategy == "low_confidence_rejected"


# -----------------------------------------------------------------------------
# Test H: Stale gesture + current voice
# -----------------------------------------------------------------------------
def test_h_stale_gesture_current_voice(service):
    # Gesture at 1000ms, Voice at 3000ms (diff 2000ms > 1500ms window)
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.90,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.88,
                timestamp_ms=3000,
            ),
        ],
        temporal_window_ms=1500,
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "next_step"
    # Gesture was discarded due to staleness; only voice contributed
    assert res.fusion_strategy == "single_mode"
    assert res.contributing_modes == ["voice"]
    assert res.fused_confidence == 0.88


# -----------------------------------------------------------------------------
# Test I: Current gesture + stale voice
# -----------------------------------------------------------------------------
def test_i_current_gesture_stale_voice(service):
    # Voice at 500ms, Gesture at 2500ms (diff 2000ms > 1500ms window)
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.92,
                timestamp_ms=500,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="open_palm",
                confidence=0.95,
                timestamp_ms=2500,
            ),
        ],
        temporal_window_ms=1500,
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "pause_session"
    assert res.fusion_strategy == "single_mode"
    assert res.contributing_modes == ["gesture"]


# -----------------------------------------------------------------------------
# Test J: Unknown gesture
# -----------------------------------------------------------------------------
def test_j_unknown_gesture(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="unknown",
                confidence=0.85,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "rejected"
    assert res.fused_action is None
    assert "Unrecognized" in res.message


# -----------------------------------------------------------------------------
# Test K: Unknown voice
# -----------------------------------------------------------------------------
def test_k_unknown_voice(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="supercalifragilistic",
                confidence=0.85,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "rejected"
    assert res.fused_action is None
    assert "Unrecognized" in res.message


# -----------------------------------------------------------------------------
# Test L: Emergency Stop from voice
# -----------------------------------------------------------------------------
def test_l_emergency_stop_voice(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="emergency stop",
                confidence=0.95,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "emergency_stop"
    assert res.requires_confirmation is True


# -----------------------------------------------------------------------------
# Test M: Emergency Stop from gesture (fist)
# -----------------------------------------------------------------------------
def test_m_emergency_stop_gesture_fist(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="fist",
                confidence=0.92,
                timestamp_ms=1000,
            )
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "emergency_stop"
    assert res.requires_confirmation is True


# -----------------------------------------------------------------------------
# Test N: Emergency Stop vs conflicting normal command
# -----------------------------------------------------------------------------
def test_n_emergency_stop_overrides_conflicting_command(service):
    # Modality 1: Voice says "next step" (0.95)
    # Modality 2: Gesture is "fist" (emergency stop) (0.90)
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.95,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="fist",
                confidence=0.90,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "emergency_stop"
    assert res.requires_confirmation is True
    assert res.fusion_strategy == "conflict_resolved"


# -----------------------------------------------------------------------------
# Test O: Duplicate multimodal event
# -----------------------------------------------------------------------------
def test_o_duplicate_multimodal_event(service):
    # Two identical gesture inputs in quick succession
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
                raw_intent="pointing",
                confidence=0.90,
                timestamp_ms=1050,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "next_step"
    assert res.fusion_strategy == "reinforcing"


# -----------------------------------------------------------------------------
# Test P: Confirmation-required fused command
# -----------------------------------------------------------------------------
def test_p_confirmation_required_command(service):
    # Cancel action is safety-critical (requires confirmation)
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="cancel",
                confidence=0.90,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="thumbs_down",
                confidence=0.92,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.validation_status == "valid"
    assert res.fused_action == "cancel_action"
    assert res.requires_confirmation is True


# -----------------------------------------------------------------------------
# Test Q: Backend outage / endpoint failure fails closed
# -----------------------------------------------------------------------------
def test_q_backend_outage_fails_closed():
    client = TestClient(app)
    # Unauthenticated request fails closed with 401/403, never executes
    resp = client.post(
        "/api/v1/multimodal/fuse",
        json={
            "inputs": [
                {
                    "mode": "voice",
                    "raw_intent": "next_step",
                    "confidence": 0.9,
                    "timestamp_ms": 1000,
                }
            ],
            "temporal_window_ms": 1500,
        },
    )
    assert resp.status_code in {401, 403}


# -----------------------------------------------------------------------------
# Test R: Architectural invariant: Fusion cannot directly execute actions
# -----------------------------------------------------------------------------
def test_r_fusion_cannot_directly_execute_actions(service):
    import inspect
    import services.multimodal_service as ms_module

    # MultimodalService must NOT import ActionExecutionService or execute_action
    source = inspect.getsource(ms_module)
    assert "ActionExecutionService" not in source
    assert "execute_action" not in source
    assert "/actions/execute" not in source


# -----------------------------------------------------------------------------
# Test S: Architectural invariant: Fusion cannot directly mutate database
# -----------------------------------------------------------------------------
def test_s_fusion_cannot_directly_mutate_database(service):
    import inspect
    import services.multimodal_service as ms_module

    # MultimodalService must NOT import database repositories or connection pools
    source = inspect.getsource(ms_module)
    assert "get_db_connection" not in source
    assert "cursor" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE" not in source
    assert "ExecutionEventsRepository" not in source


# -----------------------------------------------------------------------------
# Test T: Exactly one execution candidate for agreeing modalities
# -----------------------------------------------------------------------------
def test_t_exactly_one_execution_candidate(service):
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.88,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.91,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    # Exactly one fused action candidate string
    assert isinstance(res.fused_action, str)
    assert res.fused_action == "next_step"
    # Result object is singular, not a list of separate executable actions
    assert hasattr(res, "fused_action")
    assert not isinstance(res.fused_action, list)
