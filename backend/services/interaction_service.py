"""
Interaction and Multimodal processing service for AMAP.

Processes multimodal inputs (gesture, voice, UI) and manages interaction event logging.
Enforces the safety rule: Recognition != Intent != Authorization != Execution.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from models.interaction import (
    InteractionEventCreate,
    InteractionEventRead,
    MultimodalIntentPayload,
    MultimodalProcessingResult,
)
from repositories.actions import ActionsRepository
from repositories.interaction_events import InteractionEventsRepository


# Standard intent-to-action vocabulary mapping for AMAP
INTENT_ACTION_MAP = {
    "next": "next_step",
    "next step": "next_step",
    "swipe_right": "next_step",
    "previous": "previous_step",
    "previous step": "previous_step",
    "swipe_left": "previous_step",
    "confirm": "confirm_action",
    "thumbs_up": "confirm_action",
    "cancel": "cancel_action",
    "thumbs_down": "cancel_action",
    "help": "request_assistance",
    "raise_hand": "request_assistance",
    "pause": "pause_session",
}


class InteractionService:
    """Business logic for multimodal processing and interaction tracking."""

    def __init__(
        self,
        interaction_events_repo: Optional[InteractionEventsRepository] = None,
        actions_repo: Optional[ActionsRepository] = None,
    ) -> None:
        self.interaction_events_repo = (
            interaction_events_repo or InteractionEventsRepository()
        )
        self.actions_repo = actions_repo or ActionsRepository()

    def record_interaction_event(
        self,
        event_create: InteractionEventCreate,
    ) -> InteractionEventRead:
        """Record an interaction event in the audit trail."""
        created = self.interaction_events_repo.create(
            organization_id=event_create.organization_id,
            worker_profile_id=event_create.worker_profile_id,
            work_session_id=event_create.work_session_id,
            action_id=event_create.action_id,
            interaction_mode=event_create.interaction_mode,
            event_type=event_create.event_type,
            confidence=event_create.confidence,
            interaction_data=event_create.interaction_data,
            occurred_at=event_create.occurred_at,
        )
        return InteractionEventRead.model_validate(created)

    def process_multimodal_intent(
        self,
        payload: MultimodalIntentPayload,
        worker_profile_id: UUID,
        organization_id: UUID,
        work_session_id: Optional[UUID] = None,
    ) -> MultimodalProcessingResult:
        """
        Process a recognized raw multimodal intent.
        Evaluates confidence thresholds and determines whether confirmation is required.
        Does NOT directly execute the action.
        """
        normalized_intent = payload.raw_intent.strip().lower()
        candidate_action_name = INTENT_ACTION_MAP.get(normalized_intent)

        # Log the raw interaction event for evidence-based personalization tracking
        self.interaction_events_repo.create(
            organization_id=organization_id,
            worker_profile_id=worker_profile_id,
            work_session_id=work_session_id,
            interaction_mode=payload.mode,
            event_type=f"recognition.{payload.mode}.{normalized_intent}",
            confidence=payload.confidence,
            interaction_data=payload.context_data,
        )

        # 1. Unknown intent
        if not candidate_action_name:
            return MultimodalProcessingResult(
                recognized=False,
                action_name=None,
                confidence=payload.confidence,
                requires_confirmation=False,
                validation_status="unrecognized",
                message=f"No mapped action found for intent '{payload.raw_intent}'.",
            )

        # 2. Low confidence rejection (< 0.40)
        if payload.confidence < 0.40:
            return MultimodalProcessingResult(
                recognized=False,
                action_name=candidate_action_name,
                confidence=payload.confidence,
                requires_confirmation=False,
                validation_status="rejected",
                message="Multimodal confidence too low. Please retry or use on-screen UI.",
            )

        # 3. Medium confidence requires explicit confirmation (0.40 - 0.70)
        if payload.confidence < 0.70:
            return MultimodalProcessingResult(
                recognized=True,
                action_name=candidate_action_name,
                confidence=payload.confidence,
                requires_confirmation=True,
                validation_status="needs_confirmation",
                message=f"Action '{candidate_action_name}' detected. Please confirm to proceed.",
            )

        # 4. High confidence (>= 0.70)
        return MultimodalProcessingResult(
            recognized=True,
            action_name=candidate_action_name,
            confidence=payload.confidence,
            requires_confirmation=False,
            validation_status="valid",
            message=f"Action '{candidate_action_name}' recognized.",
        )
