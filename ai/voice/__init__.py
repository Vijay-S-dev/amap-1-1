"""
AMAP Acoustic Voice Processing & Phonetic Matching Pipeline.
"""

from ai.voice.noise_filter import AcousticNoiseFilter
from ai.voice.preprocessor import (
    compute_audio_rms,
    estimate_snr_db,
    extract_acoustic_features,
    is_voice_active,
    normalize_transcript,
)
from ai.voice.recognizer import VoiceRecognizer, compute_soundex
from ai.voice.vocabulary import COMMAND_VOCABULARY

__all__ = [
    "COMMAND_VOCABULARY",
    "AcousticNoiseFilter",
    "VoiceRecognizer",
    "compute_audio_rms",
    "compute_soundex",
    "estimate_snr_db",
    "extract_acoustic_features",
    "is_voice_active",
    "normalize_transcript",
]
