"""
Tests for AMAP Personalization and Evidence-Based Adaptation Pipeline (Phase 12).
Covers preference updates, audit history tracking, multi-event failure pattern analysis,
capability profile management, and personalization endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.worker import (
    AdaptationEvaluationResult,
    AdaptationRecommendation,
    PersonalizationHistoryRead,
    WorkerCapabilityProfileRead,
    WorkerPersonalizationRead,
)
from routes.personalization import get_personalization_service
from services.personalization_service import PersonalizationService


# =====================================================================
# Unit Tests with Mock Repositories
# =====================================================================

def test_personalization_update_and_history_tracking():
    mock_pers_repo = MagicMock()
    mock_hist_repo = MagicMock()
    mock_events_repo = MagicMock()
    mock_caps_repo = MagicMock()

    service = PersonalizationService(
        personalizations_repo=mock_pers_repo,
        history_repo=mock_hist_repo,
        interaction_events_repo=mock_events_repo,
        capabilities_repo=mock_caps_repo,
    )

    worker_id = uuid.uuid4()
    pers_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Existing personalization with dwell_time_ms = 400
    mock_pers_repo.get_by_worker_profile_id.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "interaction_configuration_id": None,
        "personalization_data": {"dwell_time_ms": 400, "ui_theme": "dark"},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    mock_pers_repo.update.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "interaction_configuration_id": None,
        "personalization_data": {"dwell_time_ms": 550, "ui_theme": "dark"},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    updated = service.update_personalization(
        worker_profile_id=worker_id,
        new_data={"dwell_time_ms": 550, "ui_theme": "dark"},
        change_reason="Increased dwell time for tremor stability",
    )

    assert updated.personalization_data["dwell_time_ms"] == 550
    # Verify history was recorded with previous state
    mock_hist_repo.create.assert_called_once_with(
        worker_personalization_id=pers_id,
        personalization_data={"dwell_time_ms": 400, "ui_theme": "dark"},
        change_reason="Increased dwell time for tremor stability",
    )


def test_evidence_adaptation_single_failure_no_change():
    """Rule: Do not change configurations on a single failure."""
    mock_events_repo = MagicMock()
    service = PersonalizationService(interaction_events_repo=mock_events_repo)
    worker_id = uuid.uuid4()

    # Only 1 single low confidence event
    mock_events_repo.list_by_worker_profile_id.return_value = [
        {"interaction_mode": "gesture", "confidence": 0.45, "event_type": "gesture_frame"}
    ]

    result = service.evaluate_and_adapt(worker_profile_id=worker_id, auto_apply=False)
    assert result.status == "stable"
    assert len(result.recommendations) == 0
    assert len(result.auto_applied_changes) == 0


def test_evidence_adaptation_repeated_gesture_dwell_increase():
    """Rule: >= 3 repeated low-confidence gestures trigger dwell time recommendation."""
    mock_pers_repo = MagicMock()
    mock_hist_repo = MagicMock()
    mock_events_repo = MagicMock()

    service = PersonalizationService(
        personalizations_repo=mock_pers_repo,
        history_repo=mock_hist_repo,
        interaction_events_repo=mock_events_repo,
    )
    worker_id = uuid.uuid4()
    pers_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_pers_repo.get_by_worker_profile_id.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "personalization_data": {"dwell_time_ms": 450},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    mock_pers_repo.update.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "interaction_configuration_id": None,
        "personalization_data": {"dwell_time_ms": 600},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    # 4 consecutive low confidence gesture events
    mock_events_repo.list_by_worker_profile_id.return_value = [
        {"interaction_mode": "gesture", "confidence": 0.40},
        {"interaction_mode": "gesture", "confidence": 0.52},
        {"interaction_mode": "gesture", "confidence": 0.48},
        {"interaction_mode": "gesture", "confidence": 0.50},
    ]

    result = service.evaluate_and_adapt(worker_profile_id=worker_id, auto_apply=True)
    assert result.status == "adapted"
    assert len(result.recommendations) == 1
    assert result.recommendations[0].recommendation_type == "dwell_time_adjustment"
    assert result.recommendations[0].suggested_value == 600  # 450 + 150
    assert len(result.auto_applied_changes) == 1


def test_evidence_adaptation_repeated_voice_noise_switch():
    """Rule: >= 3 repeated voice errors trigger modality switch recommendation (requires approval)."""
    mock_events_repo = MagicMock()
    service = PersonalizationService(interaction_events_repo=mock_events_repo)
    worker_id = uuid.uuid4()

    mock_events_repo.list_by_worker_profile_id.return_value = [
        {"interaction_mode": "voice", "confidence": 0.35},
        {"interaction_mode": "voice", "confidence": 0.42},
        {"interaction_mode": "voice", "confidence": 0.38},
    ]

    result = service.evaluate_and_adapt(worker_profile_id=worker_id, auto_apply=True)
    assert result.status == "recommendations_ready"
    assert len(result.recommendations) == 1
    assert result.recommendations[0].recommendation_type == "modality_switch_recommendation"
    assert result.recommendations[0].auto_applicable is False  # Requires supervisor/human review


def test_worker_capability_profile_management():
    mock_caps_repo = MagicMock()
    service = PersonalizationService(capabilities_repo=mock_caps_repo)
    worker_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_caps_repo.get_by_worker_profile_id.return_value = None
    mock_caps_repo.create.return_value = {
        "id": uuid.uuid4(),
        "worker_profile_id": worker_id,
        "capability_data": {
            "motor": {"fine_motor_control": "moderate_tremor", "preferred_hand": "Right"},
            "speech": {"clarity": "slight_dysarthria"},
        },
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    caps = service.update_worker_capabilities(
        worker_profile_id=worker_id,
        capability_data={
            "motor": {"fine_motor_control": "moderate_tremor", "preferred_hand": "Right"},
            "speech": {"clarity": "slight_dysarthria"},
        },
    )
    assert caps.capability_data["motor"]["fine_motor_control"] == "moderate_tremor"


# =====================================================================
# API Route Endpoint Tests
# =====================================================================

def test_personalization_endpoints_expanded():
    client = TestClient(app)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    mock_worker = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=worker_id,
    )

    mock_service = MagicMock()
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker
    app.dependency_overrides[get_personalization_service] = lambda: mock_service

    try:
        # 1. POST /evaluate-adapt
        mock_service.evaluate_and_adapt.return_value = AdaptationEvaluationResult(
            worker_profile_id=worker_id,
            status="stable",
            evidence_count=15,
            recommendations=[],
            auto_applied_changes=[],
            message="Stable interaction.",
        )
        resp1 = client.post("/api/v1/personalization/me/evaluate-adapt?auto_apply=false")
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "stable"

        # 2. GET /capabilities
        mock_service.get_worker_capabilities.return_value = WorkerCapabilityProfileRead(
            id=uuid.uuid4(),
            worker_profile_id=worker_id,
            capability_data={"motor": "normal"},
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        resp2 = client.get("/api/v1/personalization/me/capabilities")
        assert resp2.status_code == 200
        assert resp2.json()["capability_data"]["motor"] == "normal"

        # 3. GET /history
        mock_service.get_personalization_history.return_value = [
            PersonalizationHistoryRead(
                id=uuid.uuid4(),
                worker_personalization_id=uuid.uuid4(),
                change_reason="Initial setup",
                previous_state={"dwell_time_ms": 300},
                new_state={},
                created_at=datetime.now(timezone.utc),
            )
        ]
        resp3 = client.get("/api/v1/personalization/me/history")
        assert resp3.status_code == 200
        assert len(resp3.json()) == 1

    finally:
        app.dependency_overrides.clear()
