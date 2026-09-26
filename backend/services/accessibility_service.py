"""
Accessibility preferences service.

Loads and saves the authenticated user's accessibility + onboarding
preferences in PostgreSQL (user_accessibility_preferences). Validation is
strict: only known keys, correct types, and en/hi language only.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from repositories.user_accessibility_preferences import (
    UserAccessibilityPreferencesRepository,
)
from services.base import ValidationError

ALLOWED_LANGUAGES = ("en", "hi")
ALLOWED_MODALITIES = ("multimodal", "gesture", "voice", "ui")

_BOOL_KEYS = (
    "highContrast",
    "reducedMotion",
    "audioFeedback",
    "hasCompletedLanguage",
    "hasCompletedAccessibility",
    "hasCompletedGestureCalibration",
    "hasCompletedVoiceSetup",
    "hasCompletedTraining",
)
_STRING_KEYS = ("language", "modality")


class AccessibilityService:
    """Business logic for per-user accessibility preferences."""

    def __init__(
        self,
        preferences_repo: Optional[UserAccessibilityPreferencesRepository] = None,
    ) -> None:
        self.preferences_repo = (
            preferences_repo or UserAccessibilityPreferencesRepository()
        )

    def _validate(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(preferences, dict):
            raise ValidationError("preferences must be an object.")
        allowed = set(_BOOL_KEYS) | set(_STRING_KEYS) | {"textScale"}
        unknown = set(preferences) - allowed
        if unknown:
            raise ValidationError(f"Unknown preference keys: {sorted(unknown)}")

        cleaned: Dict[str, Any] = {}
        for key in _BOOL_KEYS:
            if key in preferences:
                if not isinstance(preferences[key], bool):
                    raise ValidationError(f"Preference '{key}' must be a boolean.")
                cleaned[key] = preferences[key]
        for key in _STRING_KEYS:
            if key in preferences:
                value = preferences[key]
                if not isinstance(value, str):
                    raise ValidationError(f"Preference '{key}' must be a string.")
                cleaned[key] = value
        if "language" in cleaned and cleaned["language"] not in ALLOWED_LANGUAGES:
            raise ValidationError(
                "language must be 'en' or 'hi' (English and Hindi only)."
            )
        if "modality" in cleaned and cleaned["modality"] not in ALLOWED_MODALITIES:
            raise ValidationError(
                f"modality must be one of {list(ALLOWED_MODALITIES)}."
            )
        if "textScale" in preferences:
            scale = preferences["textScale"]
            if isinstance(scale, bool) or not isinstance(scale, (int, float)):
                raise ValidationError("textScale must be a number between 1.0 and 1.5.")
            if not (1.0 <= float(scale) <= 1.5):
                raise ValidationError("textScale must be between 1.0 and 1.5.")
            cleaned["textScale"] = float(scale)
        return cleaned

    def get_preferences(self, user_id: UUID) -> Dict[str, Any]:
        """Return the user's stored preferences ({} when never saved)."""
        row = self.preferences_repo.get(user_id)
        if not row:
            return {}
        prefs = row.get("preferences") or {}
        return prefs if isinstance(prefs, dict) else {}

    def update_preferences(
        self, user_id: UUID, preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate and persist the user's preferences (full replace)."""
        cleaned = self._validate(preferences)
        row = self.preferences_repo.upsert(user_id, cleaned)
        saved = row.get("preferences") or {}
        return saved if isinstance(saved, dict) else cleaned
