"""
Tests for AMAP Multimodal Processing & Cross-Modal Fusion Pipeline (Phase 11).
Covers reinforcing fusion, complementary spatial-action binding, safety-first conflict resolution,
temporal window correlation, and the multimodal fusion API endpoint.
"""

from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.base import InteractionMode
from models.multimodal import MultimodalFusionPayload, MultimodalInputItem
from services.multimodal_service import MultimodalService


# =====================================================================
# Single Modality & Reinforcing Fusion Tests
# =====================================================================

def test_multimodal_single_mode():
    service = MultimodalService()
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
    assert res.fused_action == "next_step"
    assert res.fused_confidence == 0.88
    assert res.fusion_strategy == "single_mode"
    assert res.requires_confirmation is False


def test_multimodal_reinforcing_agreement():
    service = MultimodalService()
    # Gesture thumbs_up (0.85) and voice confirm (0.90) in same temporal window
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="thumbs_up",
                confidence=0.85,
                timestamp_ms=1000,
                context_data={"source": "camera_1"},
            ),
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="confirm",
                confidence=0.90,
                timestamp_ms=1200,
                context_data={"source": "mic_1"},
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.fused_action == "confirm_action"
    # Fused confidence: 1 - (1 - 0.85)*(1 - 0.90) = 1 - 0.15*0.10 = 0.985
    assert res.fused_confidence == pytest.approx(0.985, rel=1e-2)
    assert res.fusion_strategy == "reinforcing"
    assert set(res.contributing_modes) == {"gesture", "voice"}
    assert res.target_context["source"] == "mic_1"


# =====================================================================
# Complementary Binding Tests
# =====================================================================

def test_multimodal_complementary_binding():
    service = MultimodalService()
    # Pointing gesture at part + Voice command 'next_step'
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="pointing",
                confidence=0.90,
                timestamp_ms=1000,
                context_data={"target_part_id": "PART-4091", "spatial_x": 0.45},
            ),
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.92,
                timestamp_ms=1100,
                context_data={"action_param": "fast_track"},
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    assert res.fused_action == "next_step"
    assert res.fusion_strategy == "complementary"
    assert res.target_context["target_part_id"] == "PART-4091"
    assert res.target_context["action_param"] == "fast_track"
    assert res.fused_confidence >= 0.90


# =====================================================================
# Conflict Resolution Tests
# =====================================================================

def test_multimodal_conflict_safety_override():
    service = MultimodalService()
    # Worker says "confirm" (0.95) but gestures "cancel" / thumbs_down (0.80)
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="confirm",
                confidence=0.95,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="thumbs_down",
                confidence=0.80,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    # Safety critical negative action ('cancel_action') takes precedence
    assert res.fused_action == "cancel_action"
    assert res.fusion_strategy == "conflict_resolved"
    assert res.requires_confirmation is True


def test_multimodal_conflict_ambiguous():
    service = MultimodalService()
    # Close confidences on conflicting actions
    payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(
                mode=InteractionMode.VOICE,
                raw_intent="next step",
                confidence=0.82,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InteractionMode.GESTURE,
                raw_intent="open_palm",
                confidence=0.80,
                timestamp_ms=1100,
            ),
        ]
    )
    res = service.fuse_inputs(payload)
    # Since open_palm maps to pause_session (which is in SAFETY_CRITICAL_ACTIONS), it resolves to pause_session
    assert res.fused_action == "pause_session"
    assert res.requires_confirmation is True


# =====================================================================
# Multimodal API Endpoint Tests
# =====================================================================

def test_multimodal_fuse_api_endpoint():
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
        resp = client.post(
            "/api/v1/multimodal/fuse",
            json={
                "inputs": [
                    {
                        "mode": "gesture",
                        "raw_intent": "thumbs_up",
                        "confidence": 0.90,
                        "timestamp_ms": 1000,
                    },
                    {
                        "mode": "voice",
                        "raw_intent": "confirm",
                        "confidence": 0.95,
                        "timestamp_ms": 1150,
                    },
                ],
                "temporal_window_ms": 1500,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fused_action"] == "confirm_action"
        assert data["fusion_strategy"] == "reinforcing"
        assert data["fused_confidence"] >= 0.98

    finally:
        app.dependency_overrides.clear()
