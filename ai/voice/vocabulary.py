"""
Bounded workplace command vocabulary and semantic mapping definitions.
"""

from typing import Any, Dict, List

# Bounded vocabulary entries with synonyms, phonetic hints, and safety ratings
COMMAND_VOCABULARY: Dict[str, Dict[str, Any]] = {
    "next_step": {
        "action": "next_step",
        "phrases": [
            "next", "next step", "continue", "proceed", "forward",
            "step next", "nxt stp", "next one", "go forward",
        ],
        "phonetic_keys": ["NXT", "KNTN", "PRSD", "FRWRD"],
        "safety_critical": False,
        "description": "Advance assembly workflow to the next step",
    },
    "previous_step": {
        "action": "previous_step",
        "phrases": [
            "previous", "previous step", "back", "go back", "prev",
            "prev step", "return", "step back",
        ],
        "phonetic_keys": ["PRVS", "BK", "RTRN"],
        "safety_critical": False,
        "description": "Return to the preceding workflow step",
    },
    "confirm_action": {
        "action": "confirm_action",
        "phrases": [
            "confirm", "confirm action", "yes", "approve", "ok",
            "okay", "accept", "verify", "done", "complete",
        ],
        "phonetic_keys": ["KNFRM", "YS", "APR", "OK", "VRF"],
        "safety_critical": False,
        "description": "Confirm active pending step or prompt",
    },
    "cancel_action": {
        "action": "cancel_action",
        "phrases": [
            "cancel", "cancel action", "no", "reject", "abort",
            "dismiss", "nevermind",
        ],
        "phonetic_keys": ["KNSL", "N", "RJKT", "ABRT"],
        "safety_critical": True,
        "description": "Cancel current pending operation",
    },
    "pause_session": {
        "action": "pause_session",
        "phrases": [
            "pause", "pause session", "break", "hold on", "standby",
            "take break", "stop work",
        ],
        "phonetic_keys": ["PS", "BRK", "HLD", "STNDB"],
        "safety_critical": False,
        "description": "Temporarily pause work timer and assembly session",
    },
    "resume_session": {
        "action": "resume_session",
        "phrases": [
            "resume", "resume session", "start work", "unpause",
            "continue work", "restart",
        ],
        "phonetic_keys": ["RSM", "STRT", "UNPS"],
        "safety_critical": False,
        "description": "Resume paused assembly session",
    },
    "request_assistance": {
        "action": "request_assistance",
        "phrases": [
            "help", "call supervisor", "assistance", "need help",
            "request help", "emergency help", "supervisor",
        ],
        "phonetic_keys": ["HLP", "SPRVSR", "ASSTNS"],
        "safety_critical": False,
        "description": "Dispatch assistance ticket to supervisor queue",
    },
    "emergency_stop": {
        "action": "emergency_stop",
        "phrases": [
            "emergency", "emergency stop", "shut down", "halt",
            "all stop", "estop", "danger stop",
        ],
        "phonetic_keys": ["MRJNS", "STP", "SHTDN", "HLT"],
        "safety_critical": True,
        "description": "Trigger physical emergency lockout and halt machinery",
    },
}
