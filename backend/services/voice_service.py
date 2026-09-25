"""
Voice Command Recognition and Phonetic/Fuzzy Matching Pipeline for AMAP (§ 11, § 12, § 13, § 14).

Processes transcribed speech commands using token normalization, fuzzy string similarity
(Levenshtein/SequenceMatcher), multilingual vocabulary keyword spotting (en, es, de, hi, ta),
and safety-aware confidence thresholding.
"""

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from models.voice import VoiceCommandPayload, VoiceCommandResult


VOICE_COMMAND_VOCABULARY: Dict[str, Dict[str, Any]] = {
    "next_step": {
        "action": "next_step",
        "phrases": [
            "next", "next step", "continue", "proceed", "forward", "step next", "advance", "nxt stp",
            "siguiente", "continuar", "adelante", "proximo",
            "weiter", "vorwärts", "vorwarts", "nächster", "nachster",
            "अगला", "आगे", "अगला कदम", "agla", "aage", "agla step", "agla kadam", "agle",
            "அடுத்து", "தொடரவும்",
        ],
        "safety_critical": False,
    },
    "previous_step": {
        "action": "previous_step",
        "phrases": [
            "previous", "previous step", "back", "go back", "prev", "prev step", "return",
            "anterior", "atras", "volver", "regresar",
            "zurück", "zuruck", "vorheriger",
            "पिछला", "वापस", "pichla", "wapas",
            "முந்தைய", "பின்னால்",
        ],
        "safety_critical": False,
    },
    "confirm_action": {
        "action": "confirm_action",
        "phrases": [
            "confirm", "confirm action", "confirm this", "confirm please", "yes", "approve", "ok", "okay", "accept", "verify",
            "confirmar", "si", "listo", "correcto", "confirmado",
            "bestätigen", "bestatigen", "ja", "fertig",
            "पुष्टि", "हाँ", "सही", "pushti", "haan", "sahi",
            "உறுதி", "சரி",
        ],
        "safety_critical": False,
    },
    "cancel_action": {
        "action": "cancel_action",
        "phrases": [
            "cancel", "cancel action", "no", "reject", "abort", "dismiss",
            "cancelar", "rechazar",
            "abbrechen", "nein",
            "रद्द करें",
            "ரத்து செய்",
        ],
        "safety_critical": True,
    },
    "pause_session": {
        "action": "pause_session",
        "phrases": [
            "pause", "pause session", "break", "hold on", "standby", "take break",
            "pausa", "pausar", "espera",
            "pausieren",
            "विराम",
            "இடைநிறுத்தம்",
        ],
        "safety_critical": False,
    },
    "resume_session": {
        "action": "resume_session",
        "phrases": [
            "resume", "resume session", "start work", "unpause", "continue work",
            "reanudar",
            "fortsetzen",
            "फिर से शुरू",
            "மீண்டும் தொடங்கு",
        ],
        "safety_critical": False,
    },
    "request_assistance": {
        "action": "request_assistance",
        "phrases": [
            "help", "call supervisor", "assistance", "need help", "request help", "i need help", "support", "supervisor",
            "ayuda", "soporte", "asistencia", "necesito ayuda",
            "hilfe", "unterstützung", "unterstutzung", "brauche hilfe",
            "मदद", "सहायता", "madad", "sahayata",
            "உதவி",
        ],
        "safety_critical": False,
    },
    "emergency_stop": {
        "action": "emergency_stop",
        "phrases": [
            "emergency", "emergency stop", "shut down", "halt", "all stop", "estop", "stop",
            "emergencia", "parada de emergencia", "detener", "alto", "parar",
            "notstopp", "notfall", "notaus", "stopp", "anhalten",
            "आपातकाल", "रोकें", "रुको", "roko", "ruko",
            "அவசரம்", "நிறுத்து",
        ],
        "safety_critical": True,
    },
}


def normalize_voice_text(text: str) -> str:
    """Normalize input speech string by lowercasing and removing punctuation."""
    cleaned = re.sub(r"[^\w\s\u0900-\u097F\u0B80-\u0BFF]", "", text.lower())
    return " ".join(cleaned.split())


def compute_string_similarity(s1: str, s2: str) -> float:
    """Compute string similarity ratio [0.0, 1.0]."""
    return difflib.SequenceMatcher(None, s1, s2).ratio()


class VoiceService:
    """
    Service for speech command recognition, fuzzy keyword spotting, and intent safety checks.
    """

    def match_command(self, raw_transcript: str) -> Tuple[Optional[str], Optional[str], float, bool]:
        """
        Match transcribed text against bounded command vocabulary using token similarity.
        Returns (matched_command, action_mapping, fuzzy_score, is_safety_critical).
        """
        normalized = normalize_voice_text(raw_transcript)
        if not normalized:
            return None, None, 0.0, False

        best_command: Optional[str] = None
        best_action: Optional[str] = None
        best_score = 0.0
        is_critical = False

        for cmd_name, cmd_info in VOICE_COMMAND_VOCABULARY.items():
            for phrase in cmd_info["phrases"]:
                p_norm = normalize_voice_text(phrase)
                
                # 1. Exact match
                if normalized == p_norm:
                    return cmd_name, cmd_info["action"], 1.0, cmd_info["safety_critical"]
                
                # 2. Word boundary containment
                pattern = r"\b" + re.escape(p_norm) + r"\b"
                if re.search(pattern, normalized):
                    containment_score = 0.92
                    if containment_score > best_score:
                        best_score = containment_score
                        best_command = cmd_name
                        best_action = cmd_info["action"]
                        is_critical = cmd_info["safety_critical"]
                    continue

                # 3. Fuzzy similarity
                sim = compute_string_similarity(normalized, p_norm)
                if sim >= 0.75 and sim > best_score:
                    best_score = sim
                    best_command = cmd_name
                    best_action = cmd_info["action"]
                    is_critical = cmd_info["safety_critical"]

        # If similarity is below confidence threshold, treat as unknown
        if best_score < 0.75:
            return None, None, 0.0, False

        return best_command, best_action, round(best_score, 2), is_critical

    def process_command(
        self,
        payload: VoiceCommandPayload,
        worker_profile_id: Optional[UUID] = None,
    ) -> VoiceCommandResult:
        """
        Process a transcribed speech payload, evaluate match against command vocabulary,
        apply confidence thresholding and safety confirmation policies.
        """
        raw_text = payload.raw_transcript.strip()
        if not raw_text:
            return VoiceCommandResult(
                matched_command=None,
                action_mapping=None,
                confidence=0.0,
                fuzzy_score=0.0,
                requires_confirmation=False,
                validation_status="unmatched",
                message="Empty voice command transcript received.",
            )

        matched_cmd, action_map, fuzzy_score, is_critical = self.match_command(raw_text)

        if not matched_cmd:
            return VoiceCommandResult(
                matched_command=None,
                action_mapping=None,
                confidence=0.0,
                fuzzy_score=0.0,
                requires_confirmation=False,
                validation_status="unmatched",
                message=f"Speech transcript '{raw_text}' did not match any recognized factory command.",
            )

        # Combined confidence metric
        combined_conf = round(min(1.0, payload.confidence * fuzzy_score), 2)

        # Confidence and safety thresholding
        if combined_conf < 0.60:
            return VoiceCommandResult(
                matched_command=matched_cmd,
                action_mapping=action_map,
                confidence=combined_conf,
                fuzzy_score=fuzzy_score,
                requires_confirmation=True,
                validation_status="low_confidence",
                message=f"Low confidence ({combined_conf:.2f}) for command '{matched_cmd}'. Please repeat clearly.",
            )

        requires_conf = is_critical or combined_conf < 0.80

        return VoiceCommandResult(
            matched_command=matched_cmd,
            action_mapping=action_map,
            confidence=combined_conf,
            fuzzy_score=fuzzy_score,
            requires_confirmation=requires_conf,
            validation_status="valid",
            message=f"Voice command '{matched_cmd}' validated with confidence {combined_conf:.2f}.",
        )
