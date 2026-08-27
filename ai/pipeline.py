"""
Unified Multimodal AI Pipeline for AMAP.

Orchestrates optical hand tracking, acoustic voice command recognition,
cross-modal temporal fusion, safety interlock evaluation, and evidence-based adaptation.
"""

from typing import Dict, List, Optional, Tuple

from ai.gesture.recognizer import GestureRecognizer
from ai.intent.assistant import AIAssistant
from ai.intent.fusion import CrossModalFusionEngine
from ai.intent.safety import SafetyInterlockEvaluator
from ai.models.types import (
    AdaptationProposal,
    GestureFramePayload,
    GestureRecognitionResult,
    InputModality,
    MultimodalFusionResult,
    MultimodalInputItem,
    VoiceCommandPayload,
    VoiceCommandResult,
)
from ai.personalization.recommender import AdaptationEngine
from ai.voice.recognizer import VoiceRecognizer


class MultimodalAIPipeline:
    """
    End-to-end perception, intent recognition, safety gating, and adaptation pipeline.
    """

    def __init__(
        self,
        gesture_recognizer: Optional[GestureRecognizer] = None,
        voice_recognizer: Optional[VoiceRecognizer] = None,
        fusion_engine: Optional[CrossModalFusionEngine] = None,
        safety_evaluator: Optional[SafetyInterlockEvaluator] = None,
        adaptation_engine: Optional[AdaptationEngine] = None,
        assistant: Optional[AIAssistant] = None,
    ) -> None:
        self.gesture_recognizer = gesture_recognizer or GestureRecognizer()
        self.voice_recognizer = voice_recognizer or VoiceRecognizer()
        self.fusion_engine = fusion_engine or CrossModalFusionEngine()
        self.safety_evaluator = safety_evaluator or SafetyInterlockEvaluator()
        self.adaptation_engine = adaptation_engine or AdaptationEngine()
        self.assistant = assistant or AIAssistant()

    def process_gesture_frame(self, payload: GestureFramePayload) -> GestureRecognitionResult:
        """Process optical hand tracking frame."""
        return self.gesture_recognizer.process_frame(payload)

    def process_voice_command(self, payload: VoiceCommandPayload) -> VoiceCommandResult:
        """Process acoustic speech command."""
        return self.voice_recognizer.process_command(payload)

    def fuse_multimodal_inputs(
        self,
        inputs: List[MultimodalInputItem],
        temporal_window_ms: Optional[int] = None,
    ) -> MultimodalFusionResult:
        """Arbitrate multi-signal inputs across temporal window."""
        return self.fusion_engine.fuse(inputs, temporal_window_ms)

    def evaluate_safety_gating(
        self,
        action: str,
        confidence: float,
        is_secondary_confirmed: bool = False,
        user_roles: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Verify safety interlocks before execution dispatch."""
        return self.safety_evaluator.evaluate_execution_gating(
            action=action,
            confidence=confidence,
            is_secondary_confirmed=is_secondary_confirmed,
            user_roles=user_roles,
        )

    def evaluate_adaptations(
        self,
        worker_id: str,
        current_dwell_ms: int = 600,
        current_hitbox_factor: float = 1.0,
    ) -> List[AdaptationProposal]:
        """Evaluate worker telemetry for personalized adaptations."""
        return self.adaptation_engine.evaluate_adaptations(
            worker_id=worker_id,
            current_dwell_ms=current_dwell_ms,
            current_hitbox_factor=current_hitbox_factor,
        )
