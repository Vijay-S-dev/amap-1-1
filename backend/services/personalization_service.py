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
    AdaptationRecommendationRecord,
    PersonalizationHistoryRead,
    WorkerCapabilityProfileRead,
    WorkerPersonalizationRead,
)
from repositories.adaptation_recommendations import AdaptationRecommendationsRepository
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
        recommendations_repo: Optional[AdaptationRecommendationsRepository] = None,
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
        self.recommendations_repo = (
            recommendations_repo or AdaptationRecommendationsRepository()
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

    def _persist_pending_recommendations(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
        recommendations: List[AdaptationRecommendation],
        evidence_count: int,
        skip_types: set,
    ) -> List[AdaptationRecommendationRecord]:
        """Store pending recommendations in PostgreSQL (deduplicated by type)."""
        stored: List[AdaptationRecommendationRecord] = []
        for rec in recommendations:
            if rec.recommendation_type in skip_types:
                continue
            existing = self.recommendations_repo.find_pending(
                organization_id, worker_profile_id, rec.recommendation_type
            )
            if existing:
                stored.append(
                    AdaptationRecommendationRecord.model_validate(
                        {**existing, "worker_name": None}
                    )
                )
                continue
            row = self.recommendations_repo.create(
                organization_id=organization_id,
                worker_profile_id=worker_profile_id,
                recommendation_type=rec.recommendation_type,
                current_value=rec.current_value,
                suggested_value=rec.suggested_value,
                confidence=rec.confidence,
                reason=rec.reason,
                auto_applicable=rec.auto_applicable,
                evidence_count=evidence_count,
            )
            stored.append(
                AdaptationRecommendationRecord.model_validate({**row, "worker_name": None})
            )
        return stored

    def list_recommendations(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AdaptationRecommendationRecord]:
        """List an organization's adaptation recommendations (review queue)."""
        rows = self.recommendations_repo.list_by_organization(
            organization_id, status=status, limit=limit
        )
        return [AdaptationRecommendationRecord.model_validate(r) for r in rows]

    def review_recommendation(
        self,
        organization_id: UUID,
        recommendation_id: UUID,
        action: str,
        reviewer_id: UUID,
    ) -> AdaptationRecommendationRecord:
        """Approve (apply) or dismiss one pending recommendation."""
        row = self.recommendations_repo.get_by_id(recommendation_id)
        if not row or row["organization_id"] != organization_id:
            raise NotFoundError("Adaptation recommendation not found.")
        if row["status"] != "pending":
            from services.base import ConflictError

            raise ConflictError(
                f"Recommendation already reviewed (status={row['status']})."
            )

        if action == "approve":
            current = self.get_personalization(row["worker_profile_id"])
            new_data = dict(current.personalization_data) if current else {}
            rtype = row["recommendation_type"]
            suggested = row["suggested_value"]
            if rtype == "dwell_time_adjustment":
                new_data["dwell_time_ms"] = suggested
            elif rtype == "modality_switch_recommendation":
                new_data["preferred_modality"] = suggested
            else:
                new_data[rtype] = suggested
            self.update_personalization(
                worker_profile_id=row["worker_profile_id"],
                new_data=new_data,
                change_reason=f"Approved adaptation: {rtype}",
            )

        updated = self.recommendations_repo.update_status(
            recommendation_id, "approved" if action == "approve" else "dismissed",
            reviewer_id,
        )
        enriched = self.recommendations_repo.get_by_id(recommendation_id)
        names = self.recommendations_repo.list_by_organization(
            organization_id, status=enriched["status"], limit=100
        )
        worker_name = next(
            (n["worker_name"] for n in names if n["id"] == recommendation_id), None
        )
        return AdaptationRecommendationRecord.model_validate(
            {**enriched, "worker_name": worker_name}
        )

    def evaluate_and_adapt(
        self,
        worker_profile_id: UUID,
        auto_apply: bool = False,
        organization_id: Optional[UUID] = None,
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
        auto_applied_types: set = set()
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
                auto_applied_types.add("dwell_time_adjustment")

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

        # Persist non-applied recommendations as pending review rows so the
        # supervisor/admin queue is real PostgreSQL state (not demo arrays).
        if organization_id is not None and recommendations:
            self._persist_pending_recommendations(
                organization_id=organization_id,
                worker_profile_id=worker_profile_id,
                recommendations=recommendations,
                evidence_count=len(recent_events),
                skip_types=set(auto_applied_types),
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
