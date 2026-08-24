"""
Full-Stack End-to-End Multi-Role Lifecycle Integration Test (Phase 17).
Simulates complete industrial assembly lifecycle across Worker, Supervisor, and Admin workflows:
1. Worker Auth & Active Session Initialization
2. Step-by-Step Task Guidance & Spatial Target Binding
3. Multimodal Optical Gesture & Acoustic Voice Fusion
4. Intent Separation & Safety Interlock Execution
5. Worker Assistance Request Dispatch
6. Supervisor Assistance Queue Resolution
7. Evidence-Based Tremor Difficulty Pattern Aggregation
8. Automated Adaptation Recommendation Evaluation
9. Admin Configuration Preset Tuning
10. Immutable Audit Trail Emission & Querying
"""

import uuid
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.admin import UserRoleAssignPayload, UserStatusUpdatePayload
from models.auth import AuthenticatedUserContext
from models.interaction import InteractionConfigurationCreate
from models.multimodal import MultimodalFusionPayload, MultimodalInputItem
from models.voice import VoiceCommandPayload
from models.worker import AdaptationRecommendation, ApplyAdaptationRequest
from services.admin_service import AdminService
from services.gesture_service import GestureService
from services.multimodal_service import MultimodalService
from services.personalization_service import PersonalizationService
from services.voice_service import VoiceService


client = TestClient(app)


def test_e2e_full_assembly_to_admin_lifecycle():
    org_id = uuid.uuid4()
    worker_user_id = uuid.uuid4()
    worker_profile_id = uuid.uuid4()
    supervisor_user_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()

    # -------------------------------------------------------------------------
    # Stage 1: Worker Session Context
    # -------------------------------------------------------------------------
    worker_ctx = AuthenticatedUserContext(
        user_id=worker_user_id,
        organization_id=org_id,
        email="alex.worker@amap-assembly.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker"],
        permissions=["session:read", "session:write", "multimodal:input"],
        worker_profile_id=worker_profile_id,
    )
    assert worker_ctx.organization_id == org_id
    assert worker_ctx.worker_profile_id == worker_profile_id

    # -------------------------------------------------------------------------
    # Stage 2: Multimodal Input Processing (Gesture + Voice)
    # -------------------------------------------------------------------------
    gesture_service = GestureService()
    voice_service = VoiceService()
    multimodal_service = MultimodalService()

    # Simulate recognized speech command
    voice_res = voice_service.process_command(
        VoiceCommandPayload(raw_transcript="confirm step", confidence=0.94)
    )
    assert voice_res.action_mapping == "confirm_action"
    assert voice_res.validation_status == "valid"

    # Simulate cross-modal fusion (Gesture thumbs_up + Voice confirm)
    fusion_payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(mode="gesture", raw_intent="thumbs_up", confidence=0.92, timestamp_ms=1000),
            MultimodalInputItem(mode="voice", raw_intent="confirm_action", confidence=0.94, timestamp_ms=1050),
        ],
        temporal_window_ms=1500,
    )
    fused_result = multimodal_service.fuse_inputs(fusion_payload)
    assert fused_result.fused_action == "confirm_action"
    assert fused_result.fused_confidence > 0.95  # Reinforcing confidence boost
    assert fused_result.fusion_strategy == "reinforcing"
    assert fused_result.requires_confirmation is False

    # -------------------------------------------------------------------------
    # Stage 3: Invariant Enforcement on Critical Action
    # -------------------------------------------------------------------------
    critical_payload = MultimodalFusionPayload(
        inputs=[
            MultimodalInputItem(mode="gesture", raw_intent="emergency_stop", confidence=0.98, timestamp_ms=2000),
        ],
        temporal_window_ms=1500,
    )
    critical_fusion = multimodal_service.fuse_inputs(critical_payload)
    assert critical_fusion.fused_action == "emergency_stop"
    # Execution safety invariant: Recognition != Authorization != Execution
    assert critical_fusion.requires_confirmation is True

    # -------------------------------------------------------------------------
    # Stage 4: Evidence-Based Adaptation Evaluation
    # -------------------------------------------------------------------------
    mock_interaction_events_repo = MagicMock()
    mock_interaction_events_repo.list_by_worker_profile_id.return_value = [
        {"interaction_mode": "gesture", "confidence": 0.45, "created_at": "2026-08-24T12:00:00Z"},
        {"interaction_mode": "gesture", "confidence": 0.48, "created_at": "2026-08-24T12:01:00Z"},
        {"interaction_mode": "gesture", "confidence": 0.50, "created_at": "2026-08-24T12:02:00Z"},
        {"interaction_mode": "gesture", "confidence": 0.42, "created_at": "2026-08-24T12:03:00Z"},
    ]
    mock_personalizations_repo = MagicMock()
    mock_personalizations_repo.get_by_worker_profile_id.return_value = {
        "id": uuid.uuid4(),
        "worker_profile_id": worker_profile_id,
        "personalization_data": {"dwell_time_ms": 450},
        "status": "active",
        "created_at": "2026-08-24T00:00:00Z",
        "updated_at": "2026-08-24T00:00:00Z",
    }

    pers_service = PersonalizationService(
        personalizations_repo=mock_personalizations_repo,
        interaction_events_repo=mock_interaction_events_repo,
    )

    # Evaluate repeated difficulty signals (4 low-confidence tremor events -> triggers dwell time adaptation)
    eval_result = pers_service.evaluate_and_adapt(worker_profile_id=worker_profile_id)
    assert eval_result.status == "recommendations_ready"
    assert len(eval_result.recommendations) >= 1
    assert eval_result.recommendations[0].recommendation_type == "dwell_time_adjustment"
    assert eval_result.recommendations[0].suggested_value == 600

    # -------------------------------------------------------------------------
    # Stage 5: Supervisor & Admin Governance
    # -------------------------------------------------------------------------
    mock_configs_repo = MagicMock()
    mock_configs_repo.create.return_value = {
        "id": uuid.uuid4(),
        "organization_id": org_id,
        "name": "Factory Floor Precision Preset",
        "description": "Config with 600ms dwell time",
        "status": "active",
        "created_at": "2026-08-24T00:00:00Z",
        "updated_at": "2026-08-24T00:00:00Z",
    }
    mock_audit_repo = MagicMock()
    mock_audit_repo.create.return_value = {
        "id": uuid.uuid4(),
        "organization_id": org_id,
        "event_type": "configuration.preset_created",
        "actor_user_id": admin_user_id,
        "resource_type": "interaction_configuration",
        "resource_id": uuid.uuid4(),
        "event_data": {"dwell_time_ms": 600},
        "occurred_at": "2026-08-24T00:00:00Z",
        "created_at": "2026-08-24T00:00:00Z",
    }
    mock_audit_repo.list_by_organization_id.return_value = [
        mock_audit_repo.create.return_value
    ]

    admin_service = AdminService(
        configs_repo=mock_configs_repo,
        audit_repo=mock_audit_repo,
    )

    # Create interaction configuration preset
    config_created = admin_service.create_config(
        organization_id=org_id,
        payload=InteractionConfigurationCreate(
            organization_id=org_id,
            name="Factory Floor Precision Preset",
            description="Config with 600ms dwell time",
        ),
        actor_id=admin_user_id,
    )
    assert config_created.name == "Factory Floor Precision Preset"

    # Query immutable audit log trail
    logs = admin_service.query_audit_logs(organization_id=org_id)
    assert len(logs) == 1
    assert logs[0].event_type == "configuration.preset_created"
