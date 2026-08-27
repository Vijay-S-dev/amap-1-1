"""
AMAP Optical Gesture Recognition & Temporal Dwell Pipeline.
"""

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

__all__ = [
    "DwellAccumulator",
    "GestureRecognizer",
    "SpatialTargetDetector",
    "calculate_angle_deg",
    "calculate_jitter",
    "compute_hand_bounding_box",
    "compute_palm_center",
    "euclidean_distance_2d",
    "euclidean_distance_3d",
    "generate_synthetic_landmarks",
]
