"""
Acoustic Voice Command Recognizer, Phonetic Matcher & Keyword Spotter.
Optimized with indexed precomputed phrase tables for sub-millisecond dispatch.
"""

import difflib
from typing import Any, Dict, List, Optional, Tuple

from ai.config import (
    CONFIDENCE_THRESHOLD_VOICE,
    EXACT_MATCH_CONFIDENCE,
    FUZZY_STRING_SIMILARITY_THRESHOLD,
    PHONETIC_MATCH_CONFIDENCE,
)
from ai.models.types import VoiceCommandPayload, VoiceCommandResult
from ai.voice.noise_filter import AcousticNoiseFilter
from ai.voice.preprocessor import extract_acoustic_features, normalize_transcript
from ai.voice.vocabulary import COMMAND_VOCABULARY


def compute_soundex(word: str) -> str:
    """Compute standard American Soundex phonetic code for a word."""
    if not word:
        return ""
    word = word.upper()
    first_letter = word[0]

    char_map = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }

    encoded = [first_letter]
    last_digit = char_map.get(first_letter, "0")

    for char in word[1:]:
        digit = char_map.get(char, "0")
        if digit != "0" and digit != last_digit:
            encoded.append(digit)
            last_digit = digit
        elif digit == "0":
            last_digit = "0"

    code = "".join(encoded).ljust(4, "0")[:4]
    return code


class VoiceRecognizer:
    """
    Processes transcribed voice inputs using indexed fuzzy string matching,
    phonetic Soundex similarity, and noise-aware confidence gating.
    """

    def __init__(
        self,
        vocabulary: Optional[Dict[str, Dict[str, Any]]] = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD_VOICE,
    ) -> None:
        self.vocabulary = vocabulary or COMMAND_VOCABULARY
        self.confidence_threshold = confidence_threshold
        self.noise_filter = AcousticNoiseFilter()

        # Precompute normalized phrases and phonetic soundex signatures
        self._indexed_phrases: List[Tuple[str, str, str, bool, List[str]]] = []
        for action_name, details in self.vocabulary.items():
            is_critical = details.get("safety_critical", False)
            for phrase in details.get("phrases", []):
                p_norm = normalize_transcript(phrase)
                p_soundex = [compute_soundex(w) for w in p_norm.split()]
                self._indexed_phrases.append((action_name, phrase, p_norm, is_critical, p_soundex))

    def process_command(self, payload: VoiceCommandPayload) -> VoiceCommandResult:
        """
        Match speech transcript against bounded vocabulary.
        """
        raw_text = payload.transcript or ""
        normalized = normalize_transcript(raw_text)

        if not normalized:
            return VoiceCommandResult(
                action=None,
                matched_phrase="",
                confidence=0.0,
                is_safety_critical=False,
                raw_transcript=raw_text,
                message="Empty voice command received.",
            )

        # 1. Check acoustic clarity & noise floor
        features = payload.acoustic_features or extract_acoustic_features()
        is_clear, clarity_score = self.noise_filter.evaluate_clarity(features)
        is_noise_suppressed = not is_clear

        # 2. Fast exact match scan
        best_action: Optional[str] = None
        best_phrase: str = ""
        best_confidence: float = 0.0
        is_critical: bool = False

        normalized_words = normalized.split()
        normalized_soundex = [compute_soundex(w) for w in normalized_words]

        # Fast path: exact or substring match
        for action_name, orig_phrase, phrase_norm, is_action_critical, phrase_soundex in self._indexed_phrases:
            if normalized == phrase_norm or phrase_norm in normalized:
                best_confidence = EXACT_MATCH_CONFIDENCE
                best_action = action_name
                best_phrase = orig_phrase
                is_critical = is_action_critical
                break

        # Fallback path: fuzzy or phonetic
        if best_confidence < EXACT_MATCH_CONFIDENCE:
            for action_name, orig_phrase, phrase_norm, is_action_critical, phrase_soundex in self._indexed_phrases:
                # Phonetic Soundex match
                if phrase_soundex == normalized_soundex and best_confidence < PHONETIC_MATCH_CONFIDENCE:
                    best_confidence = PHONETIC_MATCH_CONFIDENCE
                    best_action = action_name
                    best_phrase = orig_phrase
                    is_critical = is_action_critical
                    continue

                # Fuzzy substring similarity
                sim = difflib.SequenceMatcher(None, normalized, phrase_norm).quick_ratio()
                if sim >= FUZZY_STRING_SIMILARITY_THRESHOLD and sim > best_confidence:
                    best_confidence = round(sim * 0.95, 3)
                    best_action = action_name
                    best_phrase = orig_phrase
                    is_critical = is_action_critical

        # 3. Apply noise penalty if acoustic signal is degraded
        if is_noise_suppressed and best_confidence > 0.0:
            best_confidence = round(best_confidence * 0.75, 3)

        # 4. Enforce confidence thresholding
        is_recognized = best_confidence >= self.confidence_threshold
        final_action = best_action if is_recognized else None

        return VoiceCommandResult(
            action=final_action,
            matched_phrase=best_phrase if is_recognized else "",
            confidence=best_confidence,
            is_safety_critical=is_critical if is_recognized else False,
            raw_transcript=raw_text,
            is_noise_suppressed=is_noise_suppressed,
            message="Recognized command" if is_recognized else "Confidence below threshold",
        )
