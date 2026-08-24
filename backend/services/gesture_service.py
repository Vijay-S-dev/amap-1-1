"""
Gesture Recognition and Temporal Dwell-Time Pipeline for AMAP.

Implements geometric landmark heuristic classification (MediaPipe 21 hand points)
and worker-specific temporal dwell-time state accumulation to filter involuntary
tremors and micro-twitches.
"""

import math
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from models.gesture import GestureFramePayload, GestureRecognitionResult, LandmarkPoint


# Mapping detected gestures to AMAP candidate actions
GESTURE_ACTION_MAPPING = {
    "thumbs_up": "confirm_action",
    "thumbs_down": "cancel_action",
    "open_palm": "pause_session",
    "fist": "grab_hold",
    "pointing": "point_focus",
    "pinch": "select_item",
    "swipe_right": "next_step",
    "swipe_left": "previous_step",
}


def _dist(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
    """Calculate Euclidean distance between two 3D landmarks."""
    return math.sqrt(
        (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2
    )


class GestureService:
    """
    Service for gesture classification, spatial tracking, and temporal dwell filtering.
    """

    def __init__(self) -> None:
        # In-memory dwell accumulator per worker: {worker_key: state_dict}
        self._dwell_states: Dict[str, Dict] = {}

    def classify_landmarks(
        self,
        landmarks: List[LandmarkPoint],
        handedness: str = "Right",
    ) -> Tuple[Optional[str], float]:
        """
        Heuristic geometric classification of 21 hand landmarks.
        Returns (gesture_name, confidence).
        """
        if len(landmarks) < 21:
            return None, 0.0

        wrist = landmarks[0]
        thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = landmarks[1], landmarks[2], landmarks[3], landmarks[4]
        index_mcp, index_pip, index_dip, index_tip = landmarks[5], landmarks[6], landmarks[7], landmarks[8]
        middle_mcp, middle_pip, middle_dip, middle_tip = landmarks[9], landmarks[10], landmarks[11], landmarks[12]
        ring_mcp, ring_pip, ring_dip, ring_tip = landmarks[13], landmarks[14], landmarks[15], landmarks[16]
        pinky_mcp, pinky_pip, pinky_dip, pinky_tip = landmarks[17], landmarks[18], landmarks[19], landmarks[20]

        # Determine finger extension relative to wrist distance
        index_ext = _dist(index_tip, wrist) > _dist(index_pip, wrist) * 1.15
        middle_ext = _dist(middle_tip, wrist) > _dist(middle_pip, wrist) * 1.15
        ring_ext = _dist(ring_tip, wrist) > _dist(ring_pip, wrist) * 1.15
        pinky_ext = _dist(pinky_tip, wrist) > _dist(pinky_pip, wrist) * 1.15
        thumb_ext = _dist(thumb_tip, wrist) > _dist(thumb_mcp, wrist) * 1.15

        # 1. Pinch Detection (Thumb Tip and Index Tip proximity)
        pinch_dist = _dist(thumb_tip, index_tip)
        if pinch_dist < 0.07:
            return "pinch", 0.90

        # 2. Thumbs Up: Thumb pointing upward (lower Y in screen coords), 4 fingers curled
        if (
            thumb_ext
            and thumb_tip.y < wrist.y - 0.08
            and not index_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            return "thumbs_up", 0.95

        # 3. Thumbs Down: Thumb pointing downward (higher Y in screen coords), 4 fingers curled
        if (
            thumb_ext
            and thumb_tip.y > wrist.y + 0.08
            and not index_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            return "thumbs_down", 0.95

        # 4. Pointing: Index finger extended, middle/ring/pinky curled
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "pointing", 0.92

        # 5. Open Palm: All fingers extended
        if index_ext and middle_ext and ring_ext and pinky_ext and thumb_ext:
            return "open_palm", 0.95

        # 6. Fist: All fingers curled
        if not index_ext and not middle_ext and not ring_ext and not pinky_ext and not thumb_ext:
            return "fist", 0.90

        # Default fallback
        return None, 0.0

    def process_frame(
        self,
        payload: GestureFramePayload,
        worker_profile_id: Optional[UUID] = None,
    ) -> GestureRecognitionResult:
        """
        Process an incoming video frame with landmarks, evaluate dwell time accumulation,
        and determine if a gesture trigger event has fired.
        """
        gesture_name, confidence = self.classify_landmarks(
            payload.landmarks,
            payload.handedness,
        )

        state_key = str(worker_profile_id) if worker_profile_id else "global_worker"
        ts = payload.timestamp_ms
        required_dwell = payload.dwell_time_ms or 500

        state = self._dwell_states.get(state_key, {
            "current_gesture": None,
            "start_time_ms": ts,
            "last_time_ms": ts,
            "has_triggered": False,
        })

        if gesture_name is None:
            # Reset state if hand is idle/unrecognized
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

        action_mapping = GESTURE_ACTION_MAPPING.get(gesture_name)

        return GestureRecognitionResult(
            detected_gesture=gesture_name,
            confidence=confidence,
            is_triggered=is_triggered,
            dwell_progress=dwell_progress,
            action_mapping=action_mapping,
            message=(
                f"Gesture '{gesture_name}' triggered!"
                if is_triggered
                else f"Dwell progress {int(dwell_progress * 100)}%"
            ),
        )
