"""
Evidence-based personalization and adaptation service for AMAP.

Manages worker interaction preferences, capability profiling, audit history tracking,
and evidence-based interaction analysis. Enforces the core AMAP rule:
Do NOT change configurations on a single failure; evaluate repeated patterns of difficulty.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from models.worker import (
    AdaptationEvaluationResult,
    AdaptationRecommendation,
    PersonalizationHistoryRead,
    WorkerCapabilityProfileRead,
    WorkerPersonalizationRead,
)
from repositories.interaction_events import InteractionEventsRepository
from repositories.personalization_history import PersonalizationHistoryRepository
from repositories.worker_capability_profiles import WorkerCapabilityProfilesRepository
from repositories.worker_personalizations import WorkerPersonalizationsRepository
from services.base import NotFoundError


class PersonalizationService:
    """Business logic for worker personalization, capability profiling, and evidence adaptation."""

    def __init__(
        self,
        personalizations_repo: Optional[WorkerPersonalizationsRepository] = None,
        history_repo: Optional[PersonalizationHistoryRepository] = None,
        interaction_events_repo: Optional[InteractionEventsRepository] = None,
        capabilities_repo: Optional[WorkerCapabilityProfilesRepository] = None,
    ) -> None:
        self.personalizations_repo = (
            personalizations_repo or WorkerPersonalizationsRepository()
        )
        self.history_repo = history_repo or PersonalizationHistoryRepository()
        self.interaction_events_repo = (
            interaction_events_repo or InteractionEventsRepository()
        )
        self.capabilities_repo = (
            capabilities_repo or WorkerCapabilityProfilesRepository()
        )

    def get_personalization(
        self,
        worker_profile_id: UUID,
    ) -> Optional[WorkerPersonalizationRead]:
        """Return current personalization settings for a worker profile."""
        rec = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
        if rec:
            return WorkerPersonalizationRead.model_validate(rec)
        return None

    def update_personalization(
        self,
        worker_profile_id: UUID,
        new_data: Dict[str, Any],
        change_reason: str = "Evidence-based adaptation update",
        interaction_configuration_id: Optional[UUID] = None,
    ) -> WorkerPersonalizationRead:
        """
        Update or create personalization settings and record audit history.
        """
        existing = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)

        if existing:
            # Record previous state into history
            self.history_repo.create(
                worker_personalization_id=existing["id"],
                personalization_data=existing.get("personalization_data", {}),
                change_reason=change_reason,
            )

            updated = self.personalizations_repo.update(
                worker_personalization_id=existing["id"],
                interaction_configuration_id=interaction_configuration_id
                or existing.get("interaction_configuration_id"),
                personalization_data=new_data,
                status="active",
            )
            return WorkerPersonalizationRead.model_validate(updated)

        # Create new personalization if none exists
        created = self.personalizations_repo.create(
            worker_profile_id=worker_profile_id,
            interaction_configuration_id=interaction_configuration_id,
            personalization_data=new_data,
            status="active",
        )
        return WorkerPersonalizationRead.model_validate(created)

    def get_personalization_history(
        self,
        worker_profile_id: UUID,
    ) -> List[PersonalizationHistoryRead]:
        """Return the complete personalization modification history for a worker."""
        existing = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
        if not existing:
            return []

        records = self.history_repo.list_by_worker_personalization_id(existing["id"])
        result = []
        for r in records:
            result.append(
                PersonalizationHistoryRead(
                    id=r["id"],
                    worker_personalization_id=r["worker_personalization_id"],
                    change_reason=r.get("change_reason"),
                    previous_state=r.get("personalization_data", {}),
                    new_state={},
                    created_at=r.get("changed_at") or r.get("created_at"),
                )
            )
        return result

    def get_worker_capabilities(
        self,
        worker_profile_id: UUID,
    ) -> Optional[WorkerCapabilityProfileRead]:
        """Return the physical/cognitive capability profile for a worker."""
        rec = self.capabilities_repo.get_by_worker_profile_id(worker_profile_id)
        if rec:
            return WorkerCapabilityProfileRead.model_validate(rec)
        return None

    def update_worker_capabilities(
        self,
        worker_profile_id: UUID,
        capability_data: Dict[str, Any],
        status: str = "active",
    ) -> WorkerCapabilityProfileRead:
        """Create or update a worker's capability profile."""
        existing = self.capabilities_repo.get_by_worker_profile_id(worker_profile_id)
        if existing:
            updated = self.capabilities_repo.update(
                worker_capability_profile_id=existing["id"],
                capability_data=capability_data,
                status=status,
            )
            return WorkerCapabilityProfileRead.model_validate(updated)

        created = self.capabilities_repo.create(
            worker_profile_id=worker_profile_id,
            capability_data=capability_data,
            status=status,
        )
        return WorkerCapabilityProfileRead.model_validate(created)

    def analyze_interaction_evidence(
        self,
        worker_profile_id: UUID,
    ) -> Dict[str, Any]:
        """
        Analyze recent interaction events to identify consistent difficulties
        and generate evidence-based personalization recommendations.
        """
        events = self.interaction_events_repo.list_by_worker_profile_id(worker_profile_id)
        if not events:
            return {
                "status": "insufficient_data",
                "recommendation": None,
                "evidence_count": 0,
            }

        # Analyze last 20 events
        recent_events = events[:20]
        gesture_low_confidence = 0
        voice_low_confidence = 0

        for ev in recent_events:
            conf = ev.get("confidence")
            mode = ev.get("interaction_mode")
            if conf is not None and float(conf) < 0.60:
                if mode == "gesture":
                    gesture_low_confidence += 1
                elif mode == "voice":
                    voice_low_confidence += 1

        recommendations: List[str] = []
        if gesture_low_confidence >= 3:
            recommendations.append(
                "Observed multiple low-confidence gesture interactions. Recommend increasing gesture dwell time or enabling voice confirmation."
            )
        if voice_low_confidence >= 3:
            recommendations.append(
                "Observed multiple low-confidence voice interactions. Recommend adjusting noise filter or suggesting gesture/UI fallback."
            )

        return {
            "status": "evaluated",
            "evidence_count": len(recent_events),
            "gesture_difficulty_count": gesture_low_confidence,
            "voice_difficulty_count": voice_low_confidence,
            "recommendations": recommendations,
        }

    def evaluate_and_adapt(
        self,
        worker_profile_id: UUID,
        auto_apply: bool = False,
    ) -> AdaptationEvaluationResult:
        """
        Multi-signal evidence evaluation engine for AMAP.
        Extracts repeated interaction failure patterns and formulates structured adaptations.
        """
        events = self.interaction_events_repo.list_by_worker_profile_id(worker_profile_id)
        if not events:
            return AdaptationEvaluationResult(
                worker_profile_id=worker_profile_id,
                status="insufficient_evidence",
                evidence_count=0,
                recommendations=[],
                auto_applied_changes=[],
                message="Insufficient interaction evidence to evaluate adaptation.",
            )

        recent_events = events[:30]
        gesture_fails = [e for e in recent_events if e.get("interaction_mode") == "gesture" and float(e.get("confidence") or 1.0) < 0.60]
        voice_fails = [e for e in recent_events if e.get("interaction_mode") == "voice" and float(e.get("confidence") or 1.0) < 0.60]

        current_pers = self.get_personalization(worker_profile_id)
        current_data = current_pers.personalization_data if current_pers else {}
        current_dwell = current_data.get("dwell_time_ms", 450)

        recommendations: List[AdaptationRecommendation] = []
        auto_applied: List[str] = []
        new_data = dict(current_data)

        # Rule 1: Repeated gesture tremor / dwell failure (>= 3 occurrences)
        if len(gesture_fails) >= 3:
            suggested_dwell = min(1200, current_dwell + 150)
            rec = AdaptationRecommendation(
                recommendation_type="dwell_time_adjustment",
                current_value=current_dwell,
                suggested_value=suggested_dwell,
                confidence=0.88,
                reason=(
                    f"Observed {len(gesture_fails)} repeated low-confidence gesture events. "
                    f"Increasing dwell time from {current_dwell}ms to {suggested_dwell}ms to stabilize tracking."
                ),
                auto_applicable=True,
            )
            recommendations.append(rec)

            if auto_apply:
                new_data["dwell_time_ms"] = suggested_dwell
                auto_applied.append(f"Adjusted dwell_time_ms to {suggested_dwell}")

        # Rule 2: Repeated voice acoustic failure (>= 3 occurrences)
        if len(voice_fails) >= 3:
            rec = AdaptationRecommendation(
                recommendation_type="modality_switch_recommendation",
                current_value="voice",
                suggested_value="gesture_ui_preferred",
                confidence=0.85,
                reason=(
                    f"Observed {len(voice_fails)} repeated voice recognition failures. "
                    "Recommend switching primary modality to Gesture or UI in high-noise zones."
                ),
                auto_applicable=False,  # Modality switch requires human/supervisor approval
            )
            recommendations.append(rec)

        # Apply updates if requested and changes exist
        if auto_apply and auto_applied:
            self.update_personalization(
                worker_profile_id=worker_profile_id,
                new_data=new_data,
                change_reason="Automated evidence-based adaptation",
            )

        status_str = "adapted" if auto_applied else ("recommendations_ready" if recommendations else "stable")
        return AdaptationEvaluationResult(
            worker_profile_id=worker_profile_id,
            status=status_str,
            evidence_count=len(recent_events),
            recommendations=recommendations,
            auto_applied_changes=auto_applied,
            message=(
                f"Generated {len(recommendations)} adaptation recommendations; auto-applied {len(auto_applied)} changes."
                if recommendations
                else "Worker interaction pattern is stable."
            ),
        )
