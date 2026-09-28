"""
Gesture Recognition and Temporal Dwell-Time Pipeline for AMAP.

Implements:
1. Standard MediaPipe 21-landmark geometric heuristic classification (thumbs_up, open_palm, etc.)
2. Worker-specific custom gesture training, quality validation, template synthesis, and database repository persistence (§ 24, § 25, § 26, § 27)
3. Worker-specific temporal dwell-time state accumulation and one-shot execution latches.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from models.base import EntityStatus
from models.gesture import (
    CustomGestureProfileRead,
    CustomGestureTrainPayload,
    GestureFramePayload,
    GestureRecognitionResult,
    LandmarkPoint,
)
from repositories.custom_gestures import CustomGesturesRepository


# Standard Mapping from detected gestures to AMAP candidate actions.
# Extended for the real-time interaction engine (computer/UI interaction).
# Workers can override any of these per-gesture mappings through
# worker_personalizations.personalization_data.gesture_action_map —
# see services/worker_interaction_service.py.
GESTURE_ACTION_MAPPING = {
    "thumbs_up": "confirm_action",
    "thumbs_down": "cancel_action",
    "open_palm": "pause_session",
    "fist": "emergency_stop",
    "pointing": "next_step",
    "pinch": "left_click",
    "pinch_hold": "select_item",
    "two_finger": "right_click",
    "two_finger_move": "scroll",
    "swipe_right": "next_step",
    "swipe_left": "previous_step",
    "swipe_up": "scroll_up",
    "swipe_down": "scroll_down",
}

INTENT_TO_ACTION_MAPPING = {
    "CONFIRM": "confirm_action",
    "NEXT_STEP": "next_step",
    "PAUSE": "pause_session",
    "HELP": "request_assistance",
    "EMERGENCY_STOP": "emergency_stop",
    "PREVIOUS_STEP": "previous_step",
}


def _dist(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
    """Calculate Euclidean distance between two 3D landmarks."""
    return math.sqrt(
        (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2
    )


def extract_normalized_feature_vector(landmarks: List[LandmarkPoint]) -> Tuple[Optional[List[float]], float]:
    """
    Extract a normalized 60-float feature vector from 21 MediaPipe hand landmarks.
    Normalizes wrist (index 0) to origin (0, 0, 0) and scales by palm length (dist 0 -> 9).
    Returns (feature_vector, palm_scale).
    """
    if len(landmarks) < 21:
        return None, 0.0

    wrist = landmarks[0]
    middle_mcp = landmarks[9]
    scale = _dist(wrist, middle_mcp)

    if scale < 0.015:
        return None, scale  # Hand too distant or invalid

    vector: List[float] = []
    for i in range(1, 21):
        pt = landmarks[i]
        norm_x = (pt.x - wrist.x) / scale
        norm_y = (pt.y - wrist.y) / scale
        norm_z = (pt.z - wrist.z) / scale
        vector.extend([norm_x, norm_y, norm_z])

    return vector, scale


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two feature vectors."""
    if len(v1) != len(v2) or len(v1) == 0:
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))

    if mag1 * mag2 == 0:
        return 0.0

    return max(-1.0, min(1.0, dot / (mag1 * mag2)))


def vector_distance(v1: List[float], v2: List[float]) -> float:
    """Compute Euclidean distance between two 60-float vectors."""
    if len(v1) != len(v2):
        return 999.0
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


class GestureService:
    """
    Service for gesture classification, custom gesture training/persistence,
    spatial tracking, and temporal dwell filtering.
    """

    def __init__(
        self,
        custom_repo: Optional[CustomGesturesRepository] = None,
    ) -> None:
        # In-memory dwell accumulator per worker: {worker_key: state_dict}
        self._dwell_states: Dict[str, Dict] = {}

        # Database repository for worker custom gestures
        self.custom_repo = custom_repo or CustomGesturesRepository()

        # Lazily-constructed worker interaction mapping resolver
        # (lazy to avoid a circular import with worker_interaction_service)
        self._interaction_mapping = None

    def _resolve_standard_action(self, worker_profile_id: Optional[UUID], gesture_name: str) -> Optional[str]:
        """
        Resolve a standard gesture to an action using the worker's effective
        mapping (worker override -> org preset -> canonical default).
        """
        if worker_profile_id is not None:
            try:
                if self._interaction_mapping is None:
                    from services.worker_interaction_service import WorkerInteractionService
                    self._interaction_mapping = WorkerInteractionService()
                action = self._interaction_mapping.resolve_gesture_action(
                    worker_profile_id, gesture_name
                )
                if action:
                    return action
            except Exception:
                # Mapping resolution failure falls back to canonical defaults
                pass
        return GESTURE_ACTION_MAPPING.get(gesture_name)

    # =========================================================================
    # Custom Gesture Training & Database Persistence (§ 24, § 25, § 26, § 27)
    # =========================================================================

    def train_custom_gesture(
        self,
        payload: CustomGestureTrainPayload,
        worker_profile_id: UUID,
        organization_id: UUID,
    ) -> CustomGestureProfileRead:
        """
        Train and persist a worker-specific custom gesture profile in the database.
        Validates sample completeness, scales, computes template, and commits to database.
        """
        samples = payload.samples
        if len(samples) < 5:
            raise ValueError(f"Custom gesture training requires at least 5 samples, received {len(samples)}.")

        feature_vectors: List[List[float]] = []
        scales: List[float] = []

        for idx, sample in enumerate(samples):
            if len(sample) < 21:
                raise ValueError(f"Sample {idx + 1} is incomplete (has {len(sample)} landmarks, expected 21).")

            vec, scale = extract_normalized_feature_vector(sample)
            if vec is None:
                raise ValueError(f"Sample {idx + 1} quality validation failed (hand too small or unreadable).")

            feature_vectors.append(vec)
            scales.append(scale)

        num_samples = len(feature_vectors)
        vec_len = len(feature_vectors[0])  # 60 floats

        # Compute centroid reference template
        template: List[float] = []
        for d in range(vec_len):
            avg_val = sum(fv[d] for fv in feature_vectors) / float(num_samples)
            template.append(round(avg_val, 5))

        # Compute intra-sample variance
        variances = [vector_distance(fv, template) for fv in feature_vectors]
        mean_variance = sum(variances) / float(num_samples)

        if mean_variance > 0.45:
            raise ValueError(
                f"Sample consistency score is too low (variance: {mean_variance:.2f} > 0.45). "
                "Please hold your hand steady and record clear samples."
            )

        stability_score = round(max(0.0, min(100.0, 100.0 - mean_variance * 50.0)), 1)
        action_mapping = INTENT_TO_ACTION_MAPPING.get(payload.intent.upper(), "confirm_action")

        # Save to database via repository with commit
        saved_dict = self.custom_repo.save(
            worker_id=worker_profile_id,
            organization_id=organization_id,
            gesture_name=payload.gesture_name,
            intent=payload.intent.upper(),
            action_mapping=action_mapping,
            handedness=payload.handedness,
            sample_count=num_samples,
            stability_score=stability_score,
            feature_template=template,
            version=1,
            status=EntityStatus.ACTIVE.value,
        )

        return CustomGestureProfileRead.model_validate(saved_dict)

    def get_worker_custom_gestures(
        self,
        worker_profile_id: UUID,
    ) -> List[CustomGestureProfileRead]:
        """Retrieve all active custom gesture profiles for a specific worker from database."""
        records = self.custom_repo.list_by_worker_id(worker_profile_id)
        return [CustomGestureProfileRead.model_validate(r) for r in records]

    def delete_worker_custom_gesture(
        self,
        worker_profile_id: UUID,
        gesture_id: UUID,
    ) -> bool:
        """Deactivate/delete a worker's custom gesture profile in the database."""
        return self.custom_repo.delete_by_id(gesture_id, worker_profile_id)

    # =========================================================================
    # Landmark Classification (Standard + Custom Hybrid)
    # =========================================================================

    def classify_landmarks(
        self,
        landmarks: List[LandmarkPoint],
        handedness: str = "Right",
        worker_profile_id: Optional[UUID] = None,
    ) -> Tuple[Optional[str], float, bool, Optional[CustomGestureProfileRead]]:
        """
        Classify 21 hand landmarks. Checks worker-specific custom gesture profiles from database first;
        falls back cleanly to standard geometric heuristic classification if no custom gesture matches.
        Returns: (gesture_name, confidence, is_custom, custom_profile)
        """
        if len(landmarks) < 21:
            return None, 0.0, False, None

        # 1. Evaluate Worker Custom Gesture Profiles loaded from database
        if worker_profile_id:
            custom_list = self.get_worker_custom_gestures(worker_profile_id)

            if custom_list:
                live_vec, scale = extract_normalized_feature_vector(landmarks)
                if live_vec is not None:
                    best_match: Optional[CustomGestureProfileRead] = None
                    best_conf = 0.0

                    for cp in custom_list:
                        dist_val = vector_distance(live_vec, cp.feature_template)
                        sim_val = cosine_similarity(live_vec, cp.feature_template)

                        # Combined confidence metric
                        conf = max(0.0, min(1.0, 1.0 - (dist_val / 1.35))) * max(0.0, sim_val)

                        if conf > 0.78 and conf > best_conf:
                            best_conf = conf
                            best_match = cp

                    if best_match and best_conf >= 0.78:
                        custom_gesture_name = f"custom_{best_match.intent.lower()}"
                        return custom_gesture_name, round(best_conf, 2), True, best_match

        # 2. Fallback to Standard Heuristic Geometric Classification (Preserved 100%)
        wrist = landmarks[0]
        thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = landmarks[1], landmarks[2], landmarks[3], landmarks[4]
        index_mcp, index_pip, index_dip, index_tip = landmarks[5], landmarks[6], landmarks[7], landmarks[8]
        middle_mcp, middle_pip, middle_dip, middle_tip = landmarks[9], landmarks[10], landmarks[11], landmarks[12]
        ring_mcp, ring_pip, ring_dip, ring_tip = landmarks[13], landmarks[14], landmarks[15], landmarks[16]
        pinky_mcp, pinky_pip, pinky_dip, pinky_tip = landmarks[17], landmarks[18], landmarks[19], landmarks[20]

        # Invariant: Hand Presence Gate (Layer 1) - ensure hand skeletal structure is valid
        if _dist(index_mcp, wrist) < 0.03 and _dist(middle_mcp, wrist) < 0.03:
            return None, 0.0, False, None

        index_ext = _dist(index_tip, wrist) > _dist(index_pip, wrist) * 1.15
        middle_ext = _dist(middle_tip, wrist) > _dist(middle_pip, wrist) * 1.15
        ring_ext = _dist(ring_tip, wrist) > _dist(ring_pip, wrist) * 1.15
        pinky_ext = _dist(pinky_tip, wrist) > _dist(pinky_pip, wrist) * 1.15
        thumb_ext = _dist(thumb_tip, wrist) > _dist(thumb_mcp, wrist) * 1.15

        # 1. Pinch Detection (thumb tip meets index tip)
        palm_span = _dist(index_mcp, wrist)
        pinch_dist = _dist(thumb_tip, index_tip)
        if palm_span > 0.04 and pinch_dist < 0.07:
            # Two-finger pinch guard: index+middle extended together with a
            # pinched thumb is the two-finger (right click) pose, not a tap.
            if middle_ext and not ring_ext and not pinky_ext:
                return "two_finger", 0.90, False, None
            return "pinch", 0.90, False, None

        # 2. Thumbs Up
        if (
            thumb_ext
            and thumb_tip.y < wrist.y - 0.08
            and not index_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            return "thumbs_up", 0.95, False, None

        # 3. Thumbs Down
        if (
            thumb_ext
            and thumb_tip.y > wrist.y + 0.08
            and not index_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            return "thumbs_down", 0.95, False, None

        # 4. Pointing
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "pointing", 0.92, False, None

        # 4b. Two-Finger Point (index + middle extended; right click / scroll pose)
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return "two_finger", 0.88, False, None

        # 5. Open Palm
        if index_ext and middle_ext and ring_ext and pinky_ext and thumb_ext:
            return "open_palm", 0.95, False, None

        # 6. Fist
        if not index_ext and not middle_ext and not ring_ext and not pinky_ext and not thumb_ext:
            return "fist", 0.90, False, None

        return None, 0.0, False, None

    def process_frame(
        self,
        payload: GestureFramePayload,
        worker_profile_id: Optional[UUID] = None,
    ) -> GestureRecognitionResult:
        """
        Process an incoming video frame with landmarks, evaluate dwell time accumulation,
        and determine if a gesture trigger event has fired (standard or custom).
        """
        gesture_name, confidence, is_custom, custom_profile = self.classify_landmarks(
            payload.landmarks,
            payload.handedness,
            worker_profile_id=worker_profile_id,
        )

        state_key = str(worker_profile_id) if worker_profile_id else "global_worker"
        ts = payload.timestamp_ms
        required_dwell = getattr(payload, 'dwell_time_ms', None) or 500

        state = self._dwell_states.get(state_key, {
            "current_gesture": None,
            "start_time_ms": ts,
            "last_time_ms": ts,
            "has_triggered": False,
        })

        if gesture_name is None:
            self._dwell_states[state_key] = {
                "current_gesture": None,
                "start_time_ms": ts,
                "last_time_ms": ts,
                "has_triggered": False,
            }
            return GestureRecognitionResult(
                detected_gesture=None,
                confidence=0.0,
                is_triggered=False,
                dwell_progress=0.0,
                action_mapping=None,
                is_custom=False,
                custom_gesture_id=None,
                message="No recognized gesture detected.",
            )

        # If gesture changed from previous frame, reset timer
        if state["current_gesture"] != gesture_name:
            state = {
                "current_gesture": gesture_name,
                "start_time_ms": ts,
                "last_time_ms": ts,
                "has_triggered": False,
            }
        else:
            state["last_time_ms"] = ts

        elapsed_ms = state["last_time_ms"] - state["start_time_ms"]
        dwell_progress = min(1.0, max(0.0, elapsed_ms / required_dwell))

        # Check if threshold reached and hasn't already fired for this continuous hold
        is_triggered = False
        if dwell_progress >= 1.0 and not state["has_triggered"]:
            is_triggered = True
            state["has_triggered"] = True

        self._dwell_states[state_key] = state

        if is_custom and custom_profile:
            action_mapping = custom_profile.action_mapping
            custom_id = custom_profile.id
            display_msg = (
                f"Custom Gesture '{custom_profile.gesture_name}' ({custom_profile.intent}) triggered!"
                if is_triggered
                else f"Custom Gesture Dwell: {int(dwell_progress * 100)}%"
            )
        else:
            action_mapping = self._resolve_standard_action(worker_profile_id, gesture_name)
            custom_id = None
            display_msg = (
                f"Gesture '{gesture_name}' triggered!"
                if is_triggered
                else f"Dwell progress {int(dwell_progress * 100)}%"
            )

        return GestureRecognitionResult(
            detected_gesture=gesture_name,
            confidence=confidence,
            is_triggered=is_triggered,
            dwell_progress=dwell_progress,
            action_mapping=action_mapping,
            is_custom=is_custom,
            custom_gesture_id=custom_id,
            message=display_msg,
        )
