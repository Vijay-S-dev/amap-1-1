"""
Dynamic acoustic noise cancellation filter and speech SNR estimator.
"""

from typing import List, Optional, Tuple

from ai.config import MIN_AUDIO_SNR_DB, NOISE_REDUCTION_GAIN_DB
from ai.models.types import AcousticFeatures


class AcousticNoiseFilter:
    """
    Applies adaptive spectral noise gating and clarity estimation for industrial manufacturing floors.
    """

    def __init__(
        self,
        min_snr_db: float = MIN_AUDIO_SNR_DB,
        noise_reduction_gain_db: float = NOISE_REDUCTION_GAIN_DB,
    ) -> None:
        self.min_snr_db = min_snr_db
        self.noise_reduction_gain_db = noise_reduction_gain_db
        self.adaptive_noise_floor_rms = 0.008

    def evaluate_clarity(self, features: AcousticFeatures) -> Tuple[bool, float]:
        """
        Evaluate if acoustic speech quality meets minimum factory floor confidence threshold.
        Returns (is_acceptable, quality_score [0.0 -> 1.0]).
        """
        if not features.is_speech_present:
            return False, 0.0

        snr = features.estimated_snr_db
        if snr < self.min_snr_db:
            # Low SNR environment (e.g. pneumatic tools or conveyor motors running)
            quality_score = max(0.1, snr / max(1.0, self.min_snr_db * 2.0))
            return False, round(quality_score, 2)

        quality_score = min(1.0, 0.5 + (snr / 40.0))
        return True, round(quality_score, 2)

    def apply_noise_gate(self, samples: List[float], gate_threshold: float = 0.015) -> List[float]:
        """
        Apply time-domain soft noise gate to attenuate background industrial hum.
        """
        filtered: List[float] = []
        for s in samples:
            if abs(s) < gate_threshold:
                filtered.append(s * 0.1)  # 20dB attenuation
            else:
                filtered.append(s)
        return filtered
