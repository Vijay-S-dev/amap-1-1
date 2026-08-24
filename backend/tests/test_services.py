"""
Unit tests for AMAP Business Services Layer.
Uses mocked repositories to verify business rules, state machines, and safety gates.
"""

from datetime import datetime, timezone
import uuid
from unittest.mock import MagicMock
import pytest

from models.action import ActionExecutionRequest
from models.assistance import AssistanceRequestCreate, NotificationCreate
from models.interaction import InteractionEventCreate, MultimodalIntentPayload
from services.base import (
    ConflictError,
    NotFoundError,
    SafetyViolationError,
    UnauthorizedError,
    ValidationError,
)
from services.work_session_service import WorkSessionService
from services.task_service import TaskService
from services.action_execution_service import ActionExecutionService
from services.interaction_service import InteractionService
from services.personalization_service import PersonalizationService
from services.assistance_service import AssistanceService


# =====================================================================
# Work Session Service Tests
# =====================================================================

def test_work_session_start_success():
    mock_repo = MagicMock()
    mock_repo.list_by_worker_profile_id.return_value = []
    worker_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_repo.create.return_value = {
        "id": session_id,
        "worker_profile_id": worker_id,
        "status": "active",
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }

    service = WorkSessionService(repo=mock_repo)
    result = service.start_session(worker_id)
    assert result.id == session_id
    assert result.status == "active"
    mock_repo.create.assert_called_once_with(worker_profile_id=worker_id, status="active")


def test_work_session_start_conflict():
    mock_repo = MagicMock()
    worker_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_repo.list_by_worker_profile_id.return_value = [
        {
            "id": uuid.uuid4(),
            "worker_profile_id": worker_id,
            "status": "active",
            "started_at": now,
            "ended_at": None,
            "created_at": now,
            "updated_at": now,
        }
    ]

    service = WorkSessionService(repo=mock_repo)
    with pytest.raises(ConflictError):
        service.start_session(worker_id)


def test_work_session_pause_and_resume():
    mock_repo = MagicMock()
    worker_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_repo.get_by_id.return_value = {
        "id": session_id,
        "worker_profile_id": worker_id,
        "status": "active",
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mock_repo.update_status.return_value = {
        "id": session_id,
        "worker_profile_id": worker_id,
        "status": "paused",
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }

    service = WorkSessionService(repo=mock_repo)
    paused = service.pause_session(session_id, worker_id)
    assert paused.status == "paused"

    mock_repo.get_by_id.return_value["status"] = "paused"
    mock_repo.update_status.return_value["status"] = "active"
    resumed = service.resume_session(session_id, worker_id)
    assert resumed.status == "active"


def test_work_session_end_session():
    mock_repo = MagicMock()
    worker_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_repo.get_by_id.return_value = {
        "id": session_id,
        "worker_profile_id": worker_id,
        "status": "active",
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mock_repo.end.return_value = {
        "id": session_id,
        "worker_profile_id": worker_id,
        "status": "completed",
        "started_at": now,
        "ended_at": now,
        "created_at": now,
        "updated_at": now,
    }

    service = WorkSessionService(repo=mock_repo)
    ended = service.end_session(session_id, worker_id)
    assert ended.status == "completed"


# =====================================================================
# Task Service Tests
# =====================================================================

def test_task_service_start_and_complete():
    mock_task_assignments_repo = MagicMock()
    mock_task_results_repo = MagicMock()
    worker_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assignments_repo.get_by_id.return_value = {
        "id": assignment_id,
        "task_id": task_id,
        "worker_profile_id": worker_id,
        "status": "active",
        "assigned_at": now,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mock_task_assignments_repo.update_status.return_value = {
        "id": assignment_id,
        "task_id": task_id,
        "worker_profile_id": worker_id,
        "status": "active",
        "assigned_at": now,
        "started_at": now,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mock_task_results_repo.get_by_worker_task_assignment_id.return_value = None
    mock_task_results_repo.create.return_value = {
        "id": uuid.uuid4(),
        "worker_task_assignment_id": assignment_id,
        "outcome": "completed",
        "result_data": {"barcode": "XYZ-999"},
        "notes": "Fast pick",
        "recorded_at": now,
        "created_at": now,
        "updated_at": now,
    }

    service = TaskService(
        task_assignments_repo=mock_task_assignments_repo,
        task_results_repo=mock_task_results_repo,
    )

    started = service.start_task_assignment(assignment_id, worker_id)
    assert started.id == assignment_id

    result = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=worker_id,
        outcome="completed",
        result_data={"barcode": "XYZ-999"},
        notes="Fast pick",
    )
    assert result["outcome"] == "completed"


# =====================================================================
# Action Execution Service Tests
# =====================================================================

def test_action_execution_safety_gate_success():
    mock_actions_repo = MagicMock()
    mock_requirements_repo = MagicMock()
    mock_step_actions_repo = MagicMock()
    mock_task_actions_repo = MagicMock()
    mock_events_repo = MagicMock()

    action_id = uuid.uuid4()
    mock_actions_repo.get_by_name.return_value = {
        "id": action_id,
        "name": "confirm_step",
        "display_name": "Confirm Step",
        "status": "active",
    }
    mock_requirements_repo.list_by_action_id.return_value = [
        {
            "id": uuid.uuid4(),
            "action_id": action_id,
            "status": "active",
            "requirement_type": "required_parameters",
            "requirement_data": {"keys": ["step_number"]},
        }
    ]

    service = ActionExecutionService(
        actions_repo=mock_actions_repo,
        action_requirements_repo=mock_requirements_repo,
        workflow_step_actions_repo=mock_step_actions_repo,
        task_actions_repo=mock_task_actions_repo,
        execution_events_repo=mock_events_repo,
    )

    req = ActionExecutionRequest(
        action_name="confirm_step",
        parameters={"step_number": 3},
    )

    resp = service.execute_action(
        request=req,
        worker_profile_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
    )
    assert resp.success is True
    assert resp.action_name == "confirm_step"
    mock_events_repo.create.assert_called_once()


def test_action_execution_missing_param_fails_safety():
    mock_actions_repo = MagicMock()
    mock_requirements_repo = MagicMock()
    action_id = uuid.uuid4()
    mock_actions_repo.get_by_name.return_value = {
        "id": action_id,
        "name": "confirm_step",
        "display_name": "Confirm Step",
        "status": "active",
    }
    mock_requirements_repo.list_by_action_id.return_value = [
        {
            "id": uuid.uuid4(),
            "action_id": action_id,
            "status": "active",
            "requirement_type": "required_parameters",
            "requirement_data": {"keys": ["step_number"]},
        }
    ]

    service = ActionExecutionService(
        actions_repo=mock_actions_repo,
        action_requirements_repo=mock_requirements_repo,
    )

    req = ActionExecutionRequest(
        action_name="confirm_step",
        parameters={},  # Missing step_number
    )

    with pytest.raises(SafetyViolationError):
        service.execute_action(
            request=req,
            worker_profile_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
        )


# =====================================================================
# Interaction Service Tests
# =====================================================================

def test_interaction_process_multimodal_confidence_tiers():
    mock_events_repo = MagicMock()
    service = InteractionService(interaction_events_repo=mock_events_repo)

    worker_id = uuid.uuid4()
    org_id = uuid.uuid4()

    # Tier 1: High confidence (>= 0.70)
    high_intent = MultimodalIntentPayload(
        mode="gesture",
        raw_intent="next step",
        confidence=0.85,
    )
    res_high = service.process_multimodal_intent(high_intent, worker_id, org_id)
    assert res_high.recognized is True
    assert res_high.action_name == "next_step"
    assert res_high.requires_confirmation is False

    # Tier 2: Medium confidence (0.40 - 0.70) requires confirmation
    med_intent = MultimodalIntentPayload(
        mode="gesture",
        raw_intent="next step",
        confidence=0.55,
    )
    res_med = service.process_multimodal_intent(med_intent, worker_id, org_id)
    assert res_med.recognized is True
    assert res_med.requires_confirmation is True

    # Tier 3: Low confidence (< 0.40) rejected
    low_intent = MultimodalIntentPayload(
        mode="gesture",
        raw_intent="next step",
        confidence=0.25,
    )
    res_low = service.process_multimodal_intent(low_intent, worker_id, org_id)
    assert res_low.recognized is False
    assert res_low.validation_status == "rejected"


# =====================================================================
# Personalization Service Tests
# =====================================================================

def test_personalization_update_and_evidence_analysis():
    mock_personalizations_repo = MagicMock()
    mock_history_repo = MagicMock()
    mock_events_repo = MagicMock()

    worker_id = uuid.uuid4()
    pers_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_personalizations_repo.get_by_worker_profile_id.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "interaction_configuration_id": None,
        "personalization_data": {"dwell_time_ms": 300},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    mock_personalizations_repo.update.return_value = {
        "id": pers_id,
        "worker_profile_id": worker_id,
        "interaction_configuration_id": None,
        "personalization_data": {"dwell_time_ms": 500},
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    service = PersonalizationService(
        personalizations_repo=mock_personalizations_repo,
        history_repo=mock_history_repo,
        interaction_events_repo=mock_events_repo,
    )

    updated = service.update_personalization(
        worker_profile_id=worker_id,
        new_data={"dwell_time_ms": 500},
        change_reason="Increase dwell time due to tremors",
    )
    assert updated.personalization_data["dwell_time_ms"] == 500
    mock_history_repo.create.assert_called_once()

    # Evidence evaluation with repeated low confidence
    mock_events_repo.list_by_worker_profile_id.return_value = [
        {"interaction_mode": "gesture", "confidence": 0.45} for _ in range(5)
    ]
    eval_result = service.analyze_interaction_evidence(worker_id)
    assert eval_result["gesture_difficulty_count"] == 5
    assert len(eval_result["recommendations"]) > 0


# =====================================================================
# Assistance Service Tests
# =====================================================================

def test_assistance_create_and_resolve():
    mock_assistance_repo = MagicMock()
    mock_notifications_repo = MagicMock()

    org_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_assistance_repo.create.return_value = {
        "id": req_id,
        "organization_id": org_id,
        "worker_profile_id": worker_id,
        "work_session_id": None,
        "workflow_assignment_id": None,
        "worker_task_assignment_id": None,
        "status": "open",
        "priority": "normal",
        "reason": "Need clarification on step 2",
        "request_data": {},
        "requested_at": now,
        "acknowledged_at": None,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mock_assistance_repo.get_by_id.return_value = {
        "id": req_id,
        "organization_id": org_id,
        "worker_profile_id": worker_id,
        "status": "open",
    }
    mock_assistance_repo.resolve.return_value = {
        "id": req_id,
        "organization_id": org_id,
        "worker_profile_id": worker_id,
        "work_session_id": None,
        "workflow_assignment_id": None,
        "worker_task_assignment_id": None,
        "status": "resolved",
        "priority": "normal",
        "reason": "Need clarification on step 2",
        "request_data": {},
        "requested_at": now,
        "acknowledged_at": None,
        "resolved_at": now,
        "created_at": now,
        "updated_at": now,
    }

    service = AssistanceService(
        assistance_repo=mock_assistance_repo,
        notifications_repo=mock_notifications_repo,
    )

    created = service.create_assistance_request(
        AssistanceRequestCreate(
            organization_id=org_id,
            worker_profile_id=worker_id,
            reason="Need clarification on step 2",
        )
    )
    assert created.status == "open"

    resolved = service.resolve_request(req_id, org_id)
    assert resolved.status == "resolved"
