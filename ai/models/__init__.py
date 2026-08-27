"""
AMAP AI Models package.
"""

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

__all__ = [
    "AcousticFeatures",
    "AdaptationProposal",
    "BaseClassifier",
    "BoundingBox",
    "DwellStatus",
    "FusionStrategy",
    "GeometricClassifier",
    "GestureFramePayload",
    "GestureRecognitionResult",
    "GestureType",
    "Handedness",
    "InputModality",
    "LandmarkPoint",
    "MockClassifier",
    "ModelRegistry",
    "MultimodalFusionResult",
    "MultimodalInputItem",
    "StatisticalClassifier",
    "VoiceCommandPayload",
    "VoiceCommandResult",
]
