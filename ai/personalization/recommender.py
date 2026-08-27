"""
Evidence-Based Personalization & Adaptation Recommendation Engine.

Strictly follows the Rule of Multi-Signal Evidence:
Never alters parameters on single outliers; requires >=3 difficulty signals in sliding window.
"""

from typing import Dict, List, Optional

from ai.config import (
    ADAPTATION_DIFFICULTY_THRESHOLD,
    DWELL_INCREMENT_STEP_MS,
    HITBOX_ENLARGEMENT_FACTOR,
    MAX_DWELL_TIME_MS,
    MIN_DWELL_TIME_MS,
)
from ai.models.types import AdaptationProposal
from ai.personalization.analyzer import DifficultyPatternAnalyzer, InteractionEventRecord


class AdaptationEngine:
    """
    Formulates evidence-based ergonomics and accessibility adaptation recommendations.
    """

    def __init__(self, analyzer: Optional[DifficultyPatternAnalyzer] = None) -> None:
        self.analyzer = analyzer or DifficultyPatternAnalyzer()

    def record_interaction(self, worker_id: str, record: InteractionEventRecord) -> None:
        """Feed telemetry event to underlying analyzer."""
        self.analyzer.record_event(worker_id, record)

    def evaluate_adaptations(
        self,
        worker_id: str,
        current_dwell_ms: int = 600,
        current_hitbox_factor: float = 1.0,
    ) -> List[AdaptationProposal]:
        """
        Evaluate interaction patterns and generate structured adaptation proposals.
        """
        metrics = self.analyzer.analyze_patterns(worker_id)
        proposals: List[AdaptationProposal] = []

        # 1. Motor Tremor Pattern Detection (>=3 tremor jitter events)
        if metrics["tremor_count"] >= ADAPTATION_DIFFICULTY_THRESHOLD:
            new_dwell = min(MAX_DWELL_TIME_MS, current_dwell_ms + DWELL_INCREMENT_STEP_MS)
            new_hitbox = round(current_hitbox_factor * HITBOX_ENLARGEMENT_FACTOR, 2)

            proposals.append(
                AdaptationProposal(
                    worker_id=worker_id,
                    recommendation_type="dwell_and_hitbox",
                    suggested_dwell_ms=new_dwell,
                    suggested_hitbox_factor=new_hitbox,
                    rationale=(
                        f"Detected persistent motor tremor/jitter ({metrics['tremor_count']} occurrences). "
                        f"Recommend increasing dwell time to {new_dwell}ms and enlarging hitboxes by {HITBOX_ENLARGEMENT_FACTOR:.2f}x."
                    ),
                    evidence_count=metrics["tremor_count"],
                    confidence=0.94,
                )
            )

        # 2. Dwell Timeout / Motor Fatigue Pattern (>=3 timeouts before trigger)
        elif metrics["dwell_timeout_count"] >= ADAPTATION_DIFFICULTY_THRESHOLD:
            new_dwell = max(MIN_DWELL_TIME_MS, current_dwell_ms - DWELL_INCREMENT_STEP_MS)
            proposals.append(
                AdaptationProposal(
                    worker_id=worker_id,
                    recommendation_type="dwell_time",
                    suggested_dwell_ms=new_dwell,
                    rationale=(
                        f"Detected repeated dwell timeouts/fatigue ({metrics['dwell_timeout_count']} occurrences). "
                        f"Recommend shortening dwell hold threshold to {new_dwell}ms."
                    ),
                    evidence_count=metrics["dwell_timeout_count"],
                    confidence=0.88,
                )
            )

        # 3. Acoustic Interference / Low SNR Pattern (>=4 low SNR events)
        if metrics["low_snr_count"] >= 4:
            proposals.append(
                AdaptationProposal(
                    worker_id=worker_id,
                    recommendation_type="noise_gate",
                    suggested_noise_reduction_db=15.0,
                    rationale=(
                        f"Detected high factory ambient noise ({metrics['low_snr_count']} low-SNR events). "
                        "Recommend boosting noise cancellation gate and enabling visual gesture fallback."
                    ),
                    evidence_count=metrics["low_snr_count"],
                    confidence=0.91,
                )
            )

        return proposals
