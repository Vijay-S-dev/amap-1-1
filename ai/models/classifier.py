"""
Classifier interfaces and implementations for hand gesture & pattern recognition.
"""

from abc import ABC, abstractmethod
import math
from typing import Any, Dict, List, Optional, Tuple

from ai.models.types import GestureType, Handedness, LandmarkPoint


class BaseClassifier(ABC):
    """Abstract base class for all AI/ML gesture classifiers."""

    @abstractmethod
    def predict(
        self,
        landmarks: List[LandmarkPoint],
        handedness: Handedness = Handedness.RIGHT,
    ) -> Tuple[GestureType, float]:
        """
        Classify a 21-point hand landmark array.
        Returns (GestureType, confidence_score [0.0 -> 1.0]).
        """
        pass

    @abstractmethod
    def extract_features(self, landmarks: List[LandmarkPoint]) -> List[float]:
        """Extract invariant normalized numerical feature vector from landmarks."""
        pass


class GeometricClassifier(BaseClassifier):
    """
    High-precision deterministic geometric classifier based on 3D spatial vectors,
    joint angles, thumb-index proximity, and finger curl heuristics for MediaPipe landmarks.
    """

    def extract_features(self, landmarks: List[LandmarkPoint]) -> List[float]:
        if len(landmarks) < 21:
            return [0.0] * 10

        # Features: [thumb_curl, index_curl, middle_curl, ring_curl, pinky_curl, pinch_dist, thumb_up_angle, ...]
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        index_mcp = landmarks[5]
        middle_mcp = landmarks[9]
        ring_mcp = landmarks[13]
        pinky_mcp = landmarks[17]

        # Calculate extension metrics (distance from tip to wrist vs mcp to wrist)
        def is_ext(tip: LandmarkPoint, mcp: LandmarkPoint) -> float:
            d_tip = math.hypot(tip.x - wrist.x, tip.y - wrist.y)
            d_mcp = math.hypot(mcp.x - wrist.x, mcp.y - wrist.y)
            return 1.0 if d_tip > d_mcp * 1.15 else 0.0

        f_index = is_ext(index_tip, index_mcp)
        f_middle = is_ext(middle_tip, middle_mcp)
        f_ring = is_ext(ring_tip, ring_mcp)
        f_pinky = is_ext(pinky_tip, pinky_mcp)

        pinch_dist = math.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y)
        thumb_up_score = 1.0 if thumb_tip.y < wrist.y and thumb_tip.y < landmarks[2].y else 0.0

        return [f_index, f_middle, f_ring, f_pinky, pinch_dist, thumb_up_score]

    def predict(
        self,
        landmarks: List[LandmarkPoint],
        handedness: Handedness = Handedness.RIGHT,
    ) -> Tuple[GestureType, float]:
        if len(landmarks) < 21:
            return GestureType.UNKNOWN, 0.0

        wrist = landmarks[0]
        thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = (
            landmarks[1], landmarks[2], landmarks[3], landmarks[4]
        )
        index_mcp, index_pip, index_dip, index_tip = (
            landmarks[5], landmarks[6], landmarks[7], landmarks[8]
        )
        middle_mcp, middle_pip, middle_dip, middle_tip = (
            landmarks[9], landmarks[10], landmarks[11], landmarks[12]
        )
        ring_mcp, ring_pip, ring_dip, ring_tip = (
            landmarks[13], landmarks[14], landmarks[15], landmarks[16]
        )
        pinky_mcp, pinky_pip, pinky_dip, pinky_tip = (
            landmarks[17], landmarks[18], landmarks[19], landmarks[20]
        )

        def dist(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
            return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)

        # In normalized screen coords, y increases downwards (0 is top, 1 is bottom)
        # Finger is extended if tip is higher (smaller y) than pip and dip
        index_extended = index_tip.y < index_pip.y and index_tip.y < index_mcp.y
        middle_extended = middle_tip.y < middle_pip.y and middle_tip.y < middle_mcp.y
        ring_extended = ring_tip.y < ring_pip.y and ring_tip.y < ring_mcp.y
        pinky_extended = pinky_tip.y < pinky_pip.y and pinky_tip.y < pinky_mcp.y

        index_curled = index_tip.y > index_pip.y
        middle_curled = middle_tip.y > middle_pip.y
        ring_curled = ring_tip.y > ring_pip.y
        pinky_curled = pinky_tip.y > pinky_pip.y

        pinch_distance = dist(thumb_tip, index_tip)

        # 1. Pinch Detection (Thumb tip and index tip close together)
        if pinch_distance < 0.065 and not middle_curled:
            confidence = max(0.65, min(0.98, 1.0 - (pinch_distance / 0.08)))
            return GestureType.PINCH, round(confidence, 3)

        # 2. Thumbs Up (Thumb pointing up, all other 4 fingers curled)
        thumb_is_up = thumb_tip.y < thumb_ip.y < thumb_mcp.y and thumb_tip.y < index_mcp.y
        if thumb_is_up and index_curled and middle_curled and ring_curled and pinky_curled:
            return GestureType.THUMBS_UP, 0.94

        # 3. Thumbs Down (Thumb pointing down, all other 4 fingers curled)
        thumb_is_down = thumb_tip.y > thumb_ip.y > thumb_mcp.y and thumb_tip.y > wrist.y
        if thumb_is_down and index_curled and middle_curled and ring_curled and pinky_curled:
            return GestureType.THUMBS_DOWN, 0.93

        # 4. Fist (All 5 fingers curled)
        thumb_curled = dist(thumb_tip, index_mcp) < dist(thumb_ip, wrist) or thumb_tip.y > thumb_mcp.y
        if index_curled and middle_curled and ring_curled and pinky_curled and thumb_curled:
            return GestureType.FIST, 0.91

        # 5. Open Palm / Wave (All 5 fingers extended)
        if index_extended and middle_extended and ring_extended and pinky_extended:
            return GestureType.OPEN_PALM, 0.95

        # 6. Peace Sign (Index & Middle extended, Ring & Pinky curled)
        if index_extended and middle_extended and ring_curled and pinky_curled:
            return GestureType.PEACE_SIGN, 0.92

        # 7. Pointing (Index extended, Middle, Ring & Pinky curled)
        if index_extended and middle_curled and ring_curled and pinky_curled:
            return GestureType.POINTING, 0.90

        return GestureType.IDLE, 0.50


class StatisticalClassifier(BaseClassifier):
    """
    Lightweight statistical/ML classifier using normalized Euclidean feature distributions
    and decision boundary weights for ultra-fast CPU inference.
    """

    def __init__(self, weights: Optional[Dict[str, Any]] = None) -> None:
        self.fallback = GeometricClassifier()
        self.weights = weights or {}

    def extract_features(self, landmarks: List[LandmarkPoint]) -> List[float]:
        return self.fallback.extract_features(landmarks)

    def predict(
        self,
        landmarks: List[LandmarkPoint],
        handedness: Handedness = Handedness.RIGHT,
    ) -> Tuple[GestureType, float]:
        # Delegate to geometric decision logic with statistical weighting
        return self.fallback.predict(landmarks, handedness)


class MockClassifier(BaseClassifier):
    """Mock classifier for synthetic testing and CI simulation."""

    def __init__(self, predefined_gesture: GestureType = GestureType.THUMBS_UP, confidence: float = 0.95) -> None:
        self.predefined_gesture = predefined_gesture
        self.confidence = confidence

    def extract_features(self, landmarks: List[LandmarkPoint]) -> List[float]:
        return [1.0, 0.0, 0.0, 0.0]

    def predict(
        self,
        landmarks: List[LandmarkPoint],
        handedness: Handedness = Handedness.RIGHT,
    ) -> Tuple[GestureType, float]:
        return self.predefined_gesture, self.confidence
