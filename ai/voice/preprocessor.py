"""
Audio frame preprocessing, Voice Activity Detection (VAD), and token normalization.
"""

import math
import re
from typing import List, Optional, Tuple

from ai.config import DEFAULT_ENERGY_THRESHOLD_RMS, MIN_AUDIO_SNR_DB
from ai.models.types import AcousticFeatures


def normalize_transcript(text: str) -> str:
    """
    Standardize raw speech transcript: lowercase, remove non-alphanumeric punctuation,
    and collapse whitespace.
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_audio_rms(samples: List[float]) -> float:
    """Calculate Root Mean Square (RMS) energy of PCM audio samples."""
    if not samples:
        return 0.0
    sum_sq = sum(s ** 2 for s in samples)
    return math.sqrt(sum_sq / len(samples))


def estimate_snr_db(signal_rms: float, noise_floor_rms: float = 0.005) -> float:
    """Estimate Signal-to-Noise Ratio (SNR) in decibels."""
    if noise_floor_rms <= 0 or signal_rms <= 0:
        return 0.0
    ratio = max(1e-5, signal_rms / noise_floor_rms)
    return round(20.0 * math.log10(ratio), 2)


def is_voice_active(
    rms_energy: float,
    threshold_rms: float = DEFAULT_ENERGY_THRESHOLD_RMS,
) -> bool:
    """Simple energy-based Voice Activity Detection (VAD)."""
    return rms_energy >= threshold_rms


def extract_acoustic_features(
    samples: Optional[List[float]] = None,
    noise_floor_rms: float = 0.005,
) -> AcousticFeatures:
    """Extract acoustic features from audio sample buffer."""
    if not samples:
        return AcousticFeatures(
            raw_audio_rms=0.05,
            estimated_snr_db=20.0,
            is_speech_present=True,
            noise_level_db=35.0,
        )

    rms = compute_audio_rms(samples)
    snr = estimate_snr_db(rms, noise_floor_rms)
    vad = is_voice_active(rms)

    return AcousticFeatures(
        raw_audio_rms=rms,
        estimated_snr_db=snr,
        is_speech_present=vad,
        noise_level_db=round(20.0 * math.log10(max(1e-5, noise_floor_rms)), 1),
    )
