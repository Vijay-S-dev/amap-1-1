"""
Domain models and schema definitions for the AMAP AI Subsystem.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import time


class Handedness(str, Enum):
    RIGHT = "Right"
    LEFT = "Left"
    UNKNOWN = "Unknown"


class GestureType(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    OPEN_PALM = "open_palm"
    FIST = "fist"
    POINTING = "pointing"
    PINCH = "pinch"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_LEFT = "swipe_left"
    PEACE_SIGN = "peace_sign"
    WAVE = "wave"
    IDLE = "idle"
    UNKNOWN = "unknown"


class DwellStatus(str, Enum):
    IDLE = "idle"
    DWELLING = "dwelling"
    TRIGGERED = "triggered"
    COOLDOWN = "cooldown"
    LOCKED = "locked"


class InputModality(str, Enum):
    GESTURE = "gesture"
    VOICE = "voice"
    UI = "ui"


class FusionStrategy(str, Enum):
    SINGLE_MODE = "single_mode"
    REINFORCING = "reinforcing"
    SPATIAL_COMPLEMENTARY = "spatial_complementary"
    CONFLICT_ARBITRATED = "conflict_arbitrated"
    SAFETY_INTERLOCKED = "safety_interlocked"


@dataclass
class LandmarkPoint:
    """Represents a normalized 3D hand/body landmark coordinate."""
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z, "visibility": self.visibility}


@dataclass
class BoundingBox:
    """2D Spatial target bounding box in normalized [0.0, 1.0] viewport."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    target_id: Optional[str] = None
    label: Optional[str] = None

    def contains(self, point: LandmarkPoint) -> bool:
        return (
            self.x_min <= point.x <= self.x_max
            and self.y_min <= point.y <= self.y_max
        )

    def expand(self, factor: float) -> "BoundingBox":
        """Enlarges hitbox around its center by factor (e.g. 1.25)."""
        width = self.x_max - self.x_min
        height = self.y_max - self.y_min
        cx = (self.x_min + self.x_max) / 2.0
        cy = (self.y_min + self.y_max) / 2.0
        new_w = width * factor
        new_h = height * factor
        return BoundingBox(
            x_min=max(0.0, cx - new_w / 2.0),
            y_min=max(0.0, cy - new_h / 2.0),
            x_max=min(1.0, cx + new_w / 2.0),
            y_max=min(1.0, cy + new_h / 2.0),
            target_id=self.target_id,
            label=self.label,
        )


@dataclass
class GestureFramePayload:
    """Optical hand tracking frame payload."""
    landmarks: List[LandmarkPoint]
    handedness: Handedness = Handedness.RIGHT
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    worker_id: Optional[str] = None
    target_hitboxes: List[BoundingBox] = field(default_factory=list)


@dataclass
class GestureRecognitionResult:
    """Output of gesture classification & temporal dwell analysis."""
    gesture: GestureType
    confidence: float
    dwell_status: DwellStatus
    dwell_progress: float  # 0.0 -> 1.0
    action: Optional[str] = None
    target_hit: Optional[BoundingBox] = None
    is_tremor_detected: bool = False
    smoothed_pointer: Optional[LandmarkPoint] = None
    message: Optional[str] = None


@dataclass
class AcousticFeatures:
    """Acoustic feature representation for voice input."""
    raw_audio_rms: float = 0.0
    estimated_snr_db: float = 20.0
    is_speech_present: bool = True
    noise_level_db: float = 40.0


@dataclass
class VoiceCommandPayload:
    """Voice transcription/audio payload."""
    transcript: str
    confidence: float = 1.0
    acoustic_features: Optional[AcousticFeatures] = None
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    worker_id: Optional[str] = None


@dataclass
class VoiceCommandResult:
    """Output of acoustic voice command recognition."""
    action: Optional[str]
    matched_phrase: str
    confidence: float
    is_safety_critical: bool
    is_noise_suppressed: bool = False
    raw_transcript: str = ""
    message: Optional[str] = None


@dataclass
class MultimodalInputItem:
    """Single input stream candidate inside temporal fusion window."""
    mode: InputModality
    raw_intent: str
    confidence: float
    timestamp_ms: int
    spatial_target: Optional[str] = None
    spatial_coords: Optional[Tuple[float, float]] = None


@dataclass
class MultimodalFusionResult:
    """Result of cross-modal arbitration & temporal fusion."""
    fused_action: Optional[str]
    fused_confidence: float
    fusion_strategy: FusionStrategy
    requires_confirmation: bool
    contributing_modes: List[InputModality]
    spatial_target_id: Optional[str] = None
    validation_status: str = "valid"
    message: Optional[str] = None


@dataclass
class AdaptationProposal:
    """Structured personalization recommendation for ergonomics/accessibility."""
    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    worker_id: Optional[str] = None
    recommendation_type: str = "dwell_time"  # dwell_time | hitbox_size | noise_gate | fallback_mode
    suggested_dwell_ms: Optional[int] = None
    suggested_hitbox_factor: Optional[float] = None
    suggested_noise_reduction_db: Optional[float] = None
    rationale: str = ""
    evidence_count: int = 0
    confidence: float = 0.90
    created_at: int = field(default_factory=lambda: int(time.time()))
