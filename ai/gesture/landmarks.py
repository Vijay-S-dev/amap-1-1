"""
Geometric algorithms and landmark analysis for 21-point hand tracking.
"""

import math
from typing import Dict, List, Optional, Tuple

from ai.models.types import BoundingBox, LandmarkPoint


def euclidean_distance_3d(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
    """Calculate Euclidean distance between two 3D landmarks."""
    return math.sqrt(
        (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2
    )


def euclidean_distance_2d(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
    """Calculate 2D Euclidean distance in normalized viewport space."""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def calculate_angle_deg(a: LandmarkPoint, b: LandmarkPoint, c: LandmarkPoint) -> float:
    """
    Calculate angle in degrees at vertex `b` between segments `ba` and `bc`.
    """
    v1 = (a.x - b.x, a.y - b.y, a.z - b.z)
    v2 = (c.x - b.x, c.y - b.y, c.z - b.z)

    dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
    mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2 + v1[2] ** 2)
    mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2 + v2[2] ** 2)

    if mag1 * mag2 == 0:
        return 0.0

    cosine = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cosine))


def compute_palm_center(landmarks: List[LandmarkPoint]) -> LandmarkPoint:
    """
    Compute palm center from Wrist (0), Index MCP (5), Middle MCP (9), and Pinky MCP (17).
    """
    if len(landmarks) < 21:
        return LandmarkPoint(0.5, 0.5, 0.0)

    indices = [0, 5, 9, 17]
    avg_x = sum(landmarks[i].x for i in indices) / 4.0
    avg_y = sum(landmarks[i].y for i in indices) / 4.0
    avg_z = sum(landmarks[i].z for i in indices) / 4.0

    return LandmarkPoint(x=avg_x, y=avg_y, z=avg_z)


def compute_hand_bounding_box(landmarks: List[LandmarkPoint], padding: float = 0.02) -> BoundingBox:
    """
    Compute tight 2D bounding box around hand landmarks with optional padding.
    """
    if not landmarks:
        return BoundingBox(0.0, 0.0, 1.0, 1.0)

    xs = [p.x for p in landmarks]
    ys = [p.y for p in landmarks]

    return BoundingBox(
        x_min=max(0.0, min(xs) - padding),
        y_min=max(0.0, min(ys) - padding),
        x_max=min(1.0, max(xs) + padding),
        y_max=min(1.0, max(ys) + padding),
        label="hand_bbox",
    )


def calculate_jitter(recent_positions: List[LandmarkPoint]) -> float:
    """
    Calculate high-frequency spatial tremor/jitter metric over sliding window of positions.
    Evaluates rapid directional reversals (velocity sign flips) combined with spatial dispersion.
    """
    n = len(recent_positions)
    if n < 4:
        return 0.0

    # 1. Spatial dispersion around local mean
    mean_x = sum(p.x for p in recent_positions) / n
    mean_y = sum(p.y for p in recent_positions) / n
    dispersion = math.sqrt(sum((p.x - mean_x) ** 2 + (p.y - mean_y) ** 2 for p in recent_positions) / n)

    # 2. Rapid directional oscillation count (velocity reversals)
    dx = [recent_positions[i].x - recent_positions[i - 1].x for i in range(1, n)]
    reversals = 0
    for i in range(1, len(dx)):
        if (dx[i] * dx[i - 1]) < 0:
            reversals += 1

    reversal_factor = reversals / max(1, len(dx) - 1)

    # Jitter metric is dispersion scaled by frequency of rapid directional reversals
    jitter_metric = dispersion * (1.0 + reversal_factor)
    return round(jitter_metric, 4)
