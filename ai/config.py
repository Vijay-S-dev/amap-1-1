"""
AMAP AI Subsystem Configuration & Hyperparameters.

Defines timing constraints, confidence thresholds, spatial limits, and safety constants
for optical hand tracking, acoustic voice processing, cross-modal temporal fusion,
and evidence-based personalization.
"""

from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Gesture & Optical Perception Parameters
# ---------------------------------------------------------------------------
DEFAULT_DWELL_TIME_MS: int = 600
MIN_DWELL_TIME_MS: int = 300
MAX_DWELL_TIME_MS: int = 1500
DWELL_COOLDOWN_MS: int = 400

# Tremor filter parameters (Exponential Moving Average smoothing alpha)
EMA_ALPHA_DEFAULT: float = 0.35  # lower = smoother (dampens tremors), higher = more responsive
EMA_ALPHA_HIGH_TREMOR: float = 0.20
TREMOR_JITTER_THRESHOLD: float = 0.045  # High-frequency variance threshold to flag motor tremor

# Landmark Euclidean distance thresholds (normalized 0.0 -> 1.0 coordinate space)
PINCH_THRESHOLD_NORM: float = 0.075
FINGER_CURL_THRESHOLD_DEG: float = 100.0  # Angle above which finger is considered curled
CONFIDENCE_THRESHOLD_GESTURE: float = 0.60

# ---------------------------------------------------------------------------
# Acoustic Voice Processing Parameters
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD_VOICE: float = 0.65
FUZZY_STRING_SIMILARITY_THRESHOLD: float = 0.72
PHONETIC_MATCH_CONFIDENCE: float = 0.85
EXACT_MATCH_CONFIDENCE: float = 0.98

# Voice Activity Detection (VAD) & SNR thresholds
MIN_AUDIO_SNR_DB: float = 6.0
DEFAULT_ENERGY_THRESHOLD_RMS: float = 0.02
NOISE_REDUCTION_GAIN_DB: float = 12.0

# ---------------------------------------------------------------------------
# Multimodal Temporal Fusion Parameters
# ---------------------------------------------------------------------------
DEFAULT_TEMPORAL_WINDOW_MS: int = 1500
MIN_TEMPORAL_WINDOW_MS: int = 500
MAX_TEMPORAL_WINDOW_MS: int = 2500

# Probabilistic reinforcement threshold
FUSED_CONFIDENCE_THRESHOLD_AUTO_EXEC: float = 0.85

# ---------------------------------------------------------------------------
# Safety Interlocks & High-Consequence Controls
# ---------------------------------------------------------------------------
# Actions requiring mandatory dual-confirmation or supervisor gating regardless of confidence
SAFETY_CRITICAL_ACTIONS: Set[str] = {
    "emergency_stop",
    "station_shutdown",
    "voltage_adjustment",
    "hydraulic_release",
    "cancel_action",
    "override_lockout",
}

# ---------------------------------------------------------------------------
# Evidence-Based Personalization & Adaptation
# ---------------------------------------------------------------------------
ADAPTATION_SLIDING_WINDOW_SIZE: int = 20
ADAPTATION_DIFFICULTY_THRESHOLD: int = 3  # >=3 occurrences in window triggers recommendation
DWELL_INCREMENT_STEP_MS: int = 150
HITBOX_ENLARGEMENT_FACTOR: float = 1.25

# ---------------------------------------------------------------------------
# Standard Workplace Actions & Mappings
# ---------------------------------------------------------------------------
GESTURE_TO_ACTION: Dict[str, str] = {
    "thumbs_up": "confirm_action",
    "thumbs_down": "cancel_action",
    "open_palm": "pause_session",
    "fist": "grab_hold",
    "pointing": "point_focus",
    "pinch": "select_item",
    "swipe_right": "next_step",
    "swipe_left": "previous_step",
    "peace_sign": "request_assistance",
    "wave": "request_assistance",
}

INTENT_ALIASES: Dict[str, str] = {
    "next": "next_step",
    "continue": "next_step",
    "proceed": "next_step",
    "back": "previous_step",
    "return": "previous_step",
    "prev": "previous_step",
    "confirm": "confirm_action",
    "approve": "confirm_action",
    "yes": "confirm_action",
    "ok": "confirm_action",
    "okay": "confirm_action",
    "cancel": "cancel_action",
    "abort": "cancel_action",
    "reject": "cancel_action",
    "stop": "emergency_stop",
    "estop": "emergency_stop",
    "emergency": "emergency_stop",
    "halt": "emergency_stop",
    "pause": "pause_session",
    "break": "pause_session",
    "resume": "resume_session",
    "start": "resume_session",
    "help": "request_assistance",
    "supervisor": "request_assistance",
}
