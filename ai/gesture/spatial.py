"""
Spatial target hit-testing and collision detection for accessible workstation UI.
"""

from typing import List, Optional, Tuple

from ai.gesture.landmarks import euclidean_distance_2d
from ai.models.types import BoundingBox, LandmarkPoint


class SpatialTargetDetector:
    """
    Hit-tests normalized optical pointer coordinates against interactive workstation targets.
    """

    def __init__(self, default_enlargement_factor: float = 1.0) -> None:
        self.enlargement_factor = default_enlargement_factor

    def find_intersecting_target(
        self,
        pointer: LandmarkPoint,
        targets: List[BoundingBox],
        enlargement_factor: Optional[float] = None,
    ) -> Optional[BoundingBox]:
        """
        Return the first bounding box containing the pointer.
        Applies accessibility hitbox scaling if requested.
        """
        factor = enlargement_factor or self.enlargement_factor

        for target in targets:
            active_box = target.expand(factor) if factor != 1.0 else target
            if active_box.contains(pointer):
                return target

        return None

    def find_nearest_target(
        self,
        pointer: LandmarkPoint,
        targets: List[BoundingBox],
    ) -> Tuple[Optional[BoundingBox], float]:
        """
        Find nearest target center to pointer and return (target, distance).
        """
        if not targets:
            return None, float("inf")

        min_dist = float("inf")
        nearest: Optional[BoundingBox] = None

        for target in targets:
            cx = (target.x_min + target.x_max) / 2.0
            cy = (target.y_min + target.y_max) / 2.0
            center_point = LandmarkPoint(cx, cy, 0.0)
            d = euclidean_distance_2d(pointer, center_point)

            if d < min_dist:
                min_dist = d
                nearest = target

        return nearest, min_dist
