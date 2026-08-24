"""
Voice Command Recognition and Phonetic/Fuzzy Matching Pipeline for AMAP.

Processes transcribed speech commands using token normalization, fuzzy string similarity
(Levenshtein/SequenceMatcher), vocabulary keyword spotting, and safety-aware confidence thresholding.
"""

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from models.voice import VoiceCommandPayload, VoiceCommandResult


VOICE_COMMAND_VOCABULARY: Dict[str, Dict[str, Any]] = {
    "next_step": {
        "action": "next_step",
        "phrases": ["next", "next step", "continue", "proceed", "forward", "step next", "nxt stp"],
        "safety_critical": False,
    },
    "previous_step": {
        "action": "previous_step",
        "phrases": ["previous", "previous step", "back", "go back", "prev", "prev step", "return"],
        "safety_critical": False,
    },
    "confirm_action": {
        "action": "confirm_action",
        "phrases": ["confirm", "confirm action", "yes", "approve", "ok", "okay", "accept", "verify"],
        "safety_critical": False,
    },
    "cancel_action": {
        "action": "cancel_action",
        "phrases": ["cancel", "cancel action", "no", "reject", "abort", "dismiss"],
        "safety_critical": True,
    },
    "pause_session": {
        "action": "pause_session",
        "phrases": ["pause", "pause session", "break", "hold on", "standby", "take break"],
        "safety_critical": False,
    },
    "resume_session": {
        "action": "resume_session",
        "phrases": ["resume", "resume session", "start work", "unpause", "continue work"],
        "safety_critical": False,
    },
    "request_assistance": {
        "action": "request_assistance",
        "phrases": ["help", "call supervisor", "assistance", "need help", "request help", "emergency help"],
        "safety_critical": False,
    },
    "emergency_stop": {
        "action": "emergency_stop",
        "phrases": ["emergency", "emergency stop", "shut down", "halt", "all stop", "estop"],
        "safety_critical": True,
    },
}


def _normalize_text(text: str) -> str:
    """Normalize input speech string by lowercasing and removing punctuation."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(cleaned.split())


def _similarity(s1: str, s2: str) -> float:
    """Compute string similarity ratio [0.0, 1.0]."""
    return difflib.SequenceMatcher(None, s1, s2).ratio()


class VoiceService:
    """
    Service for speech command recognition, fuzzy keyword spotting, and intent safety checks.
    """

    def match_command(self, raw_transcript: str) -> Tuple[Optional[str], Optional[str], float, bool]:
        """
        Match transcribed text against command vocabulary using normalized fuzzy token similarity.
        Returns (matched_command, action_mapping, fuzzy_score, is_safety_critical).
        """
        normalized = _normalize_text(raw_transcript)
        if not normalized:
            return None, None, 0.0, False

        best_command: Optional[str] = None
        best_action: Optional[str] = None
        best_score = 0.0
        is_critical = False

        for cmd_name, cmd_info in VOICE_COMMAND_VOCABULARY.items():
            for phrase in cmd_info["phrases"]:
                # Check exact phrase match or substring containment
                if normalized == phrase:
                    return cmd_name, cmd_info["action"], 1.0, cmd_info["safety_critical"]
                if phrase in normalized or normalized in phrase:
                    containment_score = len(phrase) / max(len(normalized), len(phrase))
                    if containment_score > best_score:
                        best_score = containment_score
                        best_command = cmd_name
                        best_action = cmd_info["action"]
                        is_critical = cmd_info["safety_critical"]

                # Fuzzy string distance
                sim = _similarity(normalized, phrase)
                if sim > best_score:
                    best_score = sim
                    best_command = cmd_name
                    best_action = cmd_info["action"]
                    is_critical = cmd_info["safety_critical"]

        return best_command, best_action, best_score, is_critical

    def process_command(
        self,
        payload: VoiceCommandPayload,
        worker_profile_id: Optional[UUID] = None,
    ) -> VoiceCommandResult:
        """
        Process a transcribed speech payload, evaluate match against command vocabulary,
        apply confidence thresholding and safety confirmation policies.
        """
        cmd_name, action_name, fuzzy_score, is_critical = self.match_command(payload.raw_transcript)
        combined_confidence = round(payload.confidence * fuzzy_score, 3)

        if cmd_name is None or fuzzy_score < 0.65 or combined_confidence < 0.50:
            return VoiceCommandResult(
                matched_command=None,
                action_mapping=None,
                confidence=combined_confidence,
                fuzzy_score=fuzzy_score,
                requires_confirmation=False,
                validation_status="unmatched",
                message=f"No matching voice command recognized for transcript '{payload.raw_transcript}'.",
            )

        # High Confidence Tier (>= 0.80)
        if combined_confidence >= 0.80 and fuzzy_score >= 0.80:
            requires_confirm = is_critical  # Safety-critical commands still require confirmation
            return VoiceCommandResult(
                matched_command=cmd_name,
                action_mapping=action_name,
                confidence=combined_confidence,
                fuzzy_score=fuzzy_score,
                requires_confirmation=requires_confirm,
                validation_status="valid",
                message=(
                    f"Voice command '{cmd_name}' recognized (safety confirmation required)."
                    if requires_confirm
                    else f"Voice command '{cmd_name}' recognized."
                ),
            )

        # Medium Confidence Tier (0.50 - 0.79)
        return VoiceCommandResult(
            matched_command=cmd_name,
            action_mapping=action_name,
            confidence=combined_confidence,
            fuzzy_score=fuzzy_score,
            requires_confirmation=True,
            validation_status="valid",
            message=f"Moderate confidence match for '{cmd_name}'. Confirmation required.",
        )
