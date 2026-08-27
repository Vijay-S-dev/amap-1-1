"""
Temporal Dwell-Time Accumulator and Involuntary Tremor Smoothing Filter.

Applies Exponential Moving Average (EMA) low-pass smoothing to spatial pointer coordinates,
filters motor tremors and micro-spasms, and tracks sustained gesture dwell duration.
"""

from collections import deque
import math
import time
from typing import Deque, Dict, Optional, Tuple

from ai.config import (
    DEFAULT_DWELL_TIME_MS,
    DWELL_COOLDOWN_MS,
    EMA_ALPHA_DEFAULT,
    EMA_ALPHA_HIGH_TREMOR,
    TREMOR_JITTER_THRESHOLD,
)
from ai.gesture.landmarks import calculate_jitter, euclidean_distance_2d
from ai.models.types import DwellStatus, GestureType, LandmarkPoint


class DwellAccumulator:
    """
    Tracks temporal dwell-time state machine for a single worker or interaction target.
    """

    def __init__(
        self,
        dwell_time_ms: int = DEFAULT_DWELL_TIME_MS,
        cooldown_ms: int = DWELL_COOLDOWN_MS,
        tolerance_radius: float = 0.085,
        buffer_size: int = 15,
    ) -> None:
        self.dwell_time_ms = dwell_time_ms
        self.cooldown_ms = cooldown_ms
        self.tolerance_radius = tolerance_radius

        self.status = DwellStatus.IDLE
        self.current_gesture: GestureType = GestureType.IDLE
        self.start_time_ms: Optional[int] = None
        self.trigger_time_ms: Optional[int] = None
        self.anchor_point: Optional[LandmarkPoint] = None

        # Position history for tremor smoothing & jitter analysis
        self._raw_history: Deque[LandmarkPoint] = deque(maxlen=buffer_size)
        self._smoothed_point: Optional[LandmarkPoint] = None
        self._is_tremor_detected: bool = False

    @property
    def smoothed_pointer(self) -> Optional[LandmarkPoint]:
        return self._smoothed_point

    @property
    def is_tremor_detected(self) -> bool:
        return self._is_tremor_detected

    def update(
        self,
        gesture: GestureType,
        raw_point: LandmarkPoint,
        timestamp_ms: Optional[int] = None,
    ) -> Tuple[DwellStatus, float]:
        """
        Feed new optical frame point into dwell state machine.
        Returns (DwellStatus, progress_fraction [0.0 -> 1.0]).
        """
        now = timestamp_ms or int(time.time() * 1000)

        # 1. Update position history and compute jitter
        self._raw_history.append(raw_point)
        jitter = calculate_jitter(list(self._raw_history))
        self._is_tremor_detected = jitter > TREMOR_JITTER_THRESHOLD

        # 2. Smooth coordinate using adaptive Exponential Moving Average (EMA)
        alpha = EMA_ALPHA_HIGH_TREMOR if self._is_tremor_detected else EMA_ALPHA_DEFAULT
        if self._smoothed_point is None:
            self._smoothed_point = LandmarkPoint(raw_point.x, raw_point.y, raw_point.z)
        else:
            self._smoothed_point = LandmarkPoint(
                x=alpha * raw_point.x + (1.0 - alpha) * self._smoothed_point.x,
                y=alpha * raw_point.y + (1.0 - alpha) * self._smoothed_point.y,
                z=alpha * raw_point.z + (1.0 - alpha) * self._smoothed_point.z,
            )

        active_point = self._smoothed_point

        # 3. Check Cooldown state
        if self.status == DwellStatus.COOLDOWN:
            if self.trigger_time_ms and (now - self.trigger_time_ms >= self.cooldown_ms):
                self._reset_to_idle()
            else:
                return DwellStatus.COOLDOWN, 0.0

        # Ignore IDLE or UNKNOWN gestures
        if gesture in (GestureType.IDLE, GestureType.UNKNOWN):
            self._reset_to_idle()
            return DwellStatus.IDLE, 0.0

        # 4. State: IDLE -> Start Dwell
        if self.status == DwellStatus.IDLE:
            self.status = DwellStatus.DWELLING
            self.current_gesture = gesture
            self.start_time_ms = now
            self.anchor_point = active_point
            return DwellStatus.DWELLING, 0.0

        # 5. State: DWELLING
        if self.status == DwellStatus.DWELLING:
            # Check if gesture changed
            if gesture != self.current_gesture:
                self.current_gesture = gesture
                self.start_time_ms = now
                self.anchor_point = active_point
                return DwellStatus.DWELLING, 0.0

            # Check if hand drifted outside tolerance radius
            if self.anchor_point:
                drift = euclidean_distance_2d(active_point, self.anchor_point)
                if drift > self.tolerance_radius:
                    # Reset dwell anchor if moved significantly
                    self.start_time_ms = now
                    self.anchor_point = active_point
                    return DwellStatus.DWELLING, 0.0

            # Calculate progress
            elapsed = now - (self.start_time_ms or now)
            progress = min(1.0, elapsed / max(1, self.dwell_time_ms))

            if progress >= 1.0:
                self.status = DwellStatus.TRIGGERED
                self.trigger_time_ms = now
                return DwellStatus.TRIGGERED, 1.0

            return DwellStatus.DWELLING, progress

        # 6. State: TRIGGERED -> Transition immediately to COOLDOWN
        if self.status == DwellStatus.TRIGGERED:
            self.status = DwellStatus.COOLDOWN
            self.trigger_time_ms = now
            return DwellStatus.COOLDOWN, 0.0

        return self.status, 0.0

    def _reset_to_idle(self) -> None:
        self.status = DwellStatus.IDLE
        self.current_gesture = GestureType.IDLE
        self.start_time_ms = None
        self.trigger_time_ms = None
        self.anchor_point = None
