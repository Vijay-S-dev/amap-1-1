"""
AMAP AI Subsystem: Multimodal Interaction, Optical Tracking, Acoustic Voice & Evidence-Based Adaptation.

Architecture Core Invariant:
    Recognition != Intent != Authorization != Execution
"""

from ai.config import (
    DEFAULT_DWELL_TIME_MS,
    DEFAULT_TEMPORAL_WINDOW_MS,
    SAFETY_CRITICAL_ACTIONS,
)
from ai.gesture.dataset import generate_synthetic_landmarks
from ai.gesture.dwell import DwellAccumulator
from ai.gesture.landmarks import (
    calculate_angle_deg,
    calculate_jitter,
    compute_hand_bounding_box,
    compute_palm_center,
    euclidean_distance_2d,
    euclidean_distance_3d,
)
from ai.gesture.recognizer import GestureRecognizer
from ai.gesture.spatial import SpatialTargetDetector
from ai.intent.assistant import AIAssistant
from ai.intent.fusion import CrossModalFusionEngine
from ai.intent.safety import SafetyInterlockEvaluator
from ai.models.classifier import (
    BaseClassifier,
    GeometricClassifier,
    MockClassifier,
    StatisticalClassifier,
)
from ai.models.registry import ModelRegistry
from ai.models.types import (
    AcousticFeatures,
    AdaptationProposal,
    BoundingBox,
    DwellStatus,
    FusionStrategy,
    GestureFramePayload,
    GestureRecognitionResult,
    GestureType,
    Handedness,
    InputModality,
    LandmarkPoint,
    MultimodalFusionResult,
    MultimodalInputItem,
    VoiceCommandPayload,
    VoiceCommandResult,
)
from ai.personalization.analyzer import (
    DifficultyPatternAnalyzer,
    InteractionEventRecord,
)
from ai.personalization.recommender import AdaptationEngine
from ai.pipeline import MultimodalAIPipeline
from ai.service import AIService
from ai.voice.noise_filter import AcousticNoiseFilter
from ai.voice.preprocessor import (
    compute_audio_rms,
    estimate_snr_db,
    extract_acoustic_features,
    is_voice_active,
    normalize_transcript,
)
from ai.voice.recognizer import VoiceRecognizer, compute_soundex
from ai.voice.vocabulary import COMMAND_VOCABULARY

__version__ = "1.0.0"

__all__ = [
    "AIAssistant",
    "AIService",
    "AcousticFeatures",
    "AcousticNoiseFilter",
    "AdaptationEngine",
    "AdaptationProposal",
    "BaseClassifier",
    "BoundingBox",
    "COMMAND_VOCABULARY",
    "CrossModalFusionEngine",
    "DEFAULT_DWELL_TIME_MS",
    "DEFAULT_TEMPORAL_WINDOW_MS",
    "DifficultyPatternAnalyzer",
    "DwellAccumulator",
    "DwellStatus",
    "FusionStrategy",
    "GeometricClassifier",
    "GestureFramePayload",
    "GestureRecognitionResult",
    "GestureRecognizer",
    "GestureType",
    "Handedness",
    "InputModality",
    "InteractionEventRecord",
    "LandmarkPoint",
    "MockClassifier",
    "ModelRegistry",
    "MultimodalAIPipeline",
    "MultimodalFusionResult",
    "MultimodalInputItem",
    "SAFETY_CRITICAL_ACTIONS",
    "SafetyInterlockEvaluator",
    "SpatialTargetDetector",
    "StatisticalClassifier",
    "VoiceCommandPayload",
    "VoiceCommandResult",
    "VoiceRecognizer",
    "__version__",
    "calculate_angle_deg",
    "calculate_jitter",
    "compute_audio_rms",
    "compute_hand_bounding_box",
    "compute_palm_center",
    "compute_soundex",
    "estimate_snr_db",
    "euclidean_distance_2d",
    "euclidean_distance_3d",
    "extract_acoustic_features",
    "generate_synthetic_landmarks",
    "is_voice_active",
    "normalize_transcript",
]
