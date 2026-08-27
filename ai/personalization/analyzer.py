"""
Multi-Signal Interaction Difficulty Analyzer for Ergonomic & Motor Diversity Adaptation.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque, Dict, List, Optional

from ai.config import ADAPTATION_SLIDING_WINDOW_SIZE


@dataclass
class InteractionEventRecord:
    """Record of a single worker interaction telemetry event."""
    timestamp: float = field(default_factory=time.time)
    mode: str = "gesture"
    success: bool = True
    is_tremor: bool = False
    is_dwell_timeout: bool = False
    is_low_snr: bool = False
    is_cancelled: bool = False
    confidence: float = 0.90


class DifficultyPatternAnalyzer:
    """
    Maintains a sliding window of recent interaction records and detects patterns
    of motor tremor, acoustic interference, or dwell fatigue.
    """

    def __init__(self, window_size: int = ADAPTATION_SLIDING_WINDOW_SIZE) -> None:
        self.window_size = window_size
        self._worker_history: Dict[str, Deque[InteractionEventRecord]] = {}

    def _get_history(self, worker_id: str) -> Deque[InteractionEventRecord]:
        if worker_id not in self._worker_history:
            self._worker_history[worker_id] = deque(maxlen=self.window_size)
        return self._worker_history[worker_id]

    def record_event(self, worker_id: str, record: InteractionEventRecord) -> None:
        """Append an interaction event to worker's sliding window."""
        history = self._get_history(worker_id)
        history.append(record)

    def analyze_patterns(self, worker_id: str) -> Dict[str, Any]:
        """
        Analyze recent history for persistent difficulty patterns.
        Returns metrics summary including tremor count, dwell timeouts, low SNR events.
        """
        history = list(self._get_history(worker_id))
        total_events = len(history)

        if total_events == 0:
            return {
                "total_events": 0,
                "tremor_count": 0,
                "dwell_timeout_count": 0,
                "low_snr_count": 0,
                "cancellation_count": 0,
                "avg_confidence": 1.0,
                "has_persistent_difficulty": False,
            }

        tremor_count = sum(1 for e in history if e.is_tremor)
        dwell_timeout_count = sum(1 for e in history if e.is_dwell_timeout)
        low_snr_count = sum(1 for e in history if e.is_low_snr)
        cancellation_count = sum(1 for e in history if e.is_cancelled)
        avg_confidence = sum(e.confidence for e in history) / total_events

        # Flag if any difficulty indicator exceeds threshold
        has_difficulty = (
            tremor_count >= 3
            or dwell_timeout_count >= 3
            or low_snr_count >= 4
            or cancellation_count >= 3
        )

        return {
            "total_events": total_events,
            "tremor_count": tremor_count,
            "dwell_timeout_count": dwell_timeout_count,
            "low_snr_count": low_snr_count,
            "cancellation_count": cancellation_count,
            "avg_confidence": round(avg_confidence, 3),
            "has_persistent_difficulty": has_difficulty,
        }
