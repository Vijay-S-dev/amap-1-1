"""
Synthetic landmark dataset generator and gesture validator.
Used for offline calibration, unit testing, and edge scenario benchmarks.
"""

import math
import random
from typing import Dict, List, Optional

from ai.models.types import GestureType, LandmarkPoint


def generate_synthetic_landmarks(
    gesture: GestureType,
    noise_level: float = 0.0,
    offset_x: float = 0.5,
    offset_y: float = 0.5,
) -> List[LandmarkPoint]:
    """
    Generate 21 normalized 3D hand landmarks matching the anatomical configuration of the requested gesture.
    """
    # Base wrist position
    landmarks: List[LandmarkPoint] = [LandmarkPoint(offset_x, offset_y, 0.0)]

    # Default relative offsets for curled fingers vs extended fingers
    if gesture == GestureType.THUMBS_UP:
        # Thumb pointing UP (negative y in screen space)
        landmarks.extend([
            LandmarkPoint(offset_x - 0.04, offset_y - 0.03, 0.0),  # 1 CMC
            LandmarkPoint(offset_x - 0.06, offset_y - 0.07, 0.0),  # 2 MCP
            LandmarkPoint(offset_x - 0.06, offset_y - 0.12, 0.0),  # 3 IP
            LandmarkPoint(offset_x - 0.06, offset_y - 0.17, 0.0),  # 4 Tip (Highest, lowest y)
        ])
        # Curled fingers (tip y > pip y)
        for i, (mcp_x, mcp_y) in enumerate([
            (offset_x - 0.02, offset_y - 0.06),  # Index
            (offset_x + 0.01, offset_y - 0.06),  # Middle
            (offset_x + 0.04, offset_y - 0.05),  # Ring
            (offset_x + 0.07, offset_y - 0.04),  # Pinky
        ]):
            landmarks.extend([
                LandmarkPoint(mcp_x, mcp_y, 0.0),            # MCP
                LandmarkPoint(mcp_x, mcp_y + 0.03, 0.0),     # PIP
                LandmarkPoint(mcp_x, mcp_y + 0.05, 0.0),     # DIP
                LandmarkPoint(mcp_x, mcp_y + 0.07, 0.0),     # Tip (curled downward)
            ])

    elif gesture == GestureType.OPEN_PALM:
        # Thumb extended
        landmarks.extend([
            LandmarkPoint(offset_x - 0.04, offset_y - 0.03, 0.0),
            LandmarkPoint(offset_x - 0.07, offset_y - 0.07, 0.0),
            LandmarkPoint(offset_x - 0.09, offset_y - 0.11, 0.0),
            LandmarkPoint(offset_x - 0.11, offset_y - 0.15, 0.0),
        ])
        # Extended fingers (tip y < pip y < mcp y)
        for i, (mcp_x, mcp_y) in enumerate([
            (offset_x - 0.03, offset_y - 0.06),
            (offset_x + 0.00, offset_y - 0.07),
            (offset_x + 0.03, offset_y - 0.06),
            (offset_x + 0.06, offset_y - 0.05),
        ]):
            landmarks.extend([
                LandmarkPoint(mcp_x, mcp_y, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.04, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.08, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.12, 0.0),
            ])

    elif gesture == GestureType.PINCH:
        # Thumb tip and index tip close together
        pinch_x, pinch_y = offset_x - 0.02, offset_y - 0.10
        landmarks.extend([
            LandmarkPoint(offset_x - 0.04, offset_y - 0.03, 0.0),
            LandmarkPoint(offset_x - 0.05, offset_y - 0.06, 0.0),
            LandmarkPoint(offset_x - 0.04, offset_y - 0.08, 0.0),
            LandmarkPoint(pinch_x, pinch_y, 0.0),  # 4 Thumb Tip
        ])
        # Index tip at pinch point
        landmarks.extend([
            LandmarkPoint(offset_x - 0.02, offset_y - 0.05, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.07, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.09, 0.0),
            LandmarkPoint(pinch_x + 0.005, pinch_y + 0.005, 0.0),  # 8 Index Tip (distance < 0.01)
        ])
        # Other fingers extended or neutral
        for i, (mcp_x, mcp_y) in enumerate([
            (offset_x + 0.01, offset_y - 0.06),
            (offset_x + 0.04, offset_y - 0.05),
            (offset_x + 0.07, offset_y - 0.04),
        ]):
            landmarks.extend([
                LandmarkPoint(mcp_x, mcp_y, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.04, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.08, 0.0),
                LandmarkPoint(mcp_x, mcp_y - 0.12, 0.0),
            ])

    elif gesture == GestureType.POINTING:
        # Thumb curled
        landmarks.extend([
            LandmarkPoint(offset_x - 0.03, offset_y - 0.02, 0.0),
            LandmarkPoint(offset_x - 0.04, offset_y - 0.04, 0.0),
            LandmarkPoint(offset_x - 0.03, offset_y - 0.05, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.05, 0.0),
        ])
        # Index extended
        landmarks.extend([
            LandmarkPoint(offset_x - 0.02, offset_y - 0.06, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.10, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.14, 0.0),
            LandmarkPoint(offset_x - 0.02, offset_y - 0.18, 0.0),  # 8 Tip extended
        ])
        # Other 3 curled
        for i, (mcp_x, mcp_y) in enumerate([
            (offset_x + 0.01, offset_y - 0.05),
            (offset_x + 0.04, offset_y - 0.04),
            (offset_x + 0.07, offset_y - 0.03),
        ]):
            landmarks.extend([
                LandmarkPoint(mcp_x, mcp_y, 0.0),
                LandmarkPoint(mcp_x, mcp_y + 0.02, 0.0),
                LandmarkPoint(mcp_x, mcp_y + 0.04, 0.0),
                LandmarkPoint(mcp_x, mcp_y + 0.06, 0.0),
            ])

    else:
        # Default neutral/idle hand
        for i in range(1, 21):
            landmarks.append(LandmarkPoint(offset_x + (i % 5) * 0.02, offset_y - (i // 5) * 0.03, 0.0))

    # Add Gaussian jitter if noise_level > 0
    if noise_level > 0.0:
        for pt in landmarks:
            pt.x += random.gauss(0, noise_level)
            pt.y += random.gauss(0, noise_level)
            pt.z += random.gauss(0, noise_level * 0.5)

    return landmarks
