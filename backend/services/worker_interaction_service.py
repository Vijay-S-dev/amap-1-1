"""
Worker Interaction Mapping Service for AMAP.

Provides the authoritative, PostgreSQL-backed resolution of:

  gesture -> action

Resolution precedence (highest wins):
  1. Worker personalization override
     (worker_personalizations.personalization_data.gesture_action_map)
  2. Organization interaction preset mapping
     (gesture_configurations joined via the worker's interaction_configuration_id)
  3. Canonical AMAP default gesture mapping (code-level fallback)

Also exposes worker interaction calibration settings persisted alongside the
gesture map in worker_personalizations.personalization_data:
  dwell_time_ms, click_debounce_ms, cursor_sensitivity, scroll_sensitivity,
  smoothing_alpha, jitter_threshold, handedness, enabled_gestures.

Nothing here is localStorage-based: every override lives in PostgreSQL and
survives refreshes, re-login, and backend restarts.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from repositories.actions import ActionsRepository
from repositories.gesture_configurations import GestureConfigurationsRepository
from repositories.worker_personalizations import WorkerPersonalizationsRepository
from services.gesture_service import GESTURE_ACTION_MAPPING
from services.personalization_service import PersonalizationService

# Canonical default gesture vocabulary recognized by the platform.
# Kept in sync with the frontend engine (frontend/worker/lib/handPoses.ts)
# and the server-side geometric classifier in services/gesture_service.py.
# GESTURE_ACTION_MAPPING already carries the full canonical set including
# the real-time interaction engine gestures (pinch/two_finger/swipes/scrolls).
# (pointing keeps its canonical next_step mapping; the workstation engine
#  additionally uses the pointing pose to drive the virtual pointer)
DEFAULT_GESTURE_ACTION_MAP: Dict[str, str] = dict(GESTURE_ACTION_MAPPING)

# Calibration defaults shared by the frontend gesture engine.
DEFAULT_CALIBRATION: Dict[str, Any] = {
    "dwell_time_ms": 500,
    "click_debounce_ms": 700,
    "double_click_window_ms": 400,
    "pinch_click_max_ms": 450,
    "pinch_select_min_ms": 650,
    "pinch_drag_min_ms": 350,
    "cursor_sensitivity": 1.4,
    "scroll_sensitivity": 220,
    "scroll_throttle_ms": 180,
    "smoothing_alpha": 0.35,
    "jitter_threshold": 0.012,
    "handedness": "Either",
    "enabled_gestures": {
        "pinch": True,
        "pinch_hold": True,
        "two_finger": True,
        "swipe_up": True,
        "swipe_down": True,
        "swipe_left": True,
        "swipe_right": True,
        "thumbs_up": True,
        "thumbs_down": True,
        "open_palm": True,
        "fist": True,
    },
}

# Known AMAP actions that a gesture may be mapped to. Used to validate
# worker-provided overrides so a mapping can never reference a non-existent
# action (the /actions/execute gateway would reject it anyway — this keeps
# errors early and friendly).
_CACHE_TTL_SECONDS = 30.0


class WorkerInteractionService:
    """Resolves worker-specific gesture mappings and calibration from PostgreSQL."""

    def __init__(
        self,
        personalizations_repo: Optional[WorkerPersonalizationsRepository] = None,
        gesture_configs_repo: Optional[GestureConfigurationsRepository] = None,
        actions_repo: Optional[ActionsRepository] = None,
        personalization_service: Optional[PersonalizationService] = None,
    ) -> None:
        self.personalizations_repo = (
            personalizations_repo or WorkerPersonalizationsRepository()
        )
        self.gesture_configs_repo = (
            gesture_configs_repo or GestureConfigurationsRepository()
        )
        self.actions_repo = actions_repo or ActionsRepository()
        self.personalization_service = (
            personalization_service or PersonalizationService(
                personalizations_repo=self.personalizations_repo
            )
        )
        # action-name cache: (cached_at, {name: id})
        self._action_names_cache: Tuple[float, Dict[str, UUID]] = (0.0, {})

    # ------------------------------------------------------------------
    # Registered action lookup (database-driven, cached briefly)
    # ------------------------------------------------------------------

    def _known_action_names(self) -> Dict[str, UUID]:
        """Return registered active action names from the actions table (cached)."""
        now = time.monotonic()
        cached_at, cached = self._action_names_cache
        if cached and (now - cached_at) < _CACHE_TTL_SECONDS:
            return cached
        try:
            names: Dict[str, UUID] = {}
            for action in self.actions_repo.list_all():
                if action.get("status") == "active":
                    names[action["name"]] = action["id"]
            self._action_names_cache = (now, names)
            return names
        except Exception:
            # Database unavailable — degrade to canonical action set so
            # recognition still resolves; execution gateway will fail loudly.
            return {}

    # ------------------------------------------------------------------
    # Mapping resolution
    # ------------------------------------------------------------------

    def _preset_mapping(self, interaction_configuration_id: Optional[UUID]) -> Dict[str, str]:
        """Gesture -> action mapping from the org interaction preset (if any)."""
        if not interaction_configuration_id:
            return {}
        mapping: Dict[str, str] = {}
        try:
            configs = self.gesture_configs_repo.list_by_interaction_configuration_id(
                interaction_configuration_id
            )
        except Exception:
            return {}
        known = self._known_action_names()
        id_to_name = {aid: name for name, aid in known.items()}
        for cfg in configs:
            if not cfg.get("is_enabled"):
                continue
            action_id = cfg.get("action_id")
            action_name = id_to_name.get(action_id)
            if action_name:
                mapping[cfg["gesture_name"]] = action_name
        return mapping

    def _worker_overrides(self, worker_profile_id: UUID) -> Dict[str, str]:
        """Worker-level gesture mapping overrides from worker_personalizations."""
        try:
            rec = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
        except Exception:
            return {}
        if not rec:
            return {}
        data = rec.get("personalization_data") or {}
        overrides = data.get("gesture_action_map") or {}
        if not isinstance(overrides, dict):
            return {}
        return {str(k): str(v) for k, v in overrides.items()}

    def get_worker_raw_personalization(self, worker_profile_id: UUID) -> Dict[str, Any]:
        """Return raw personalization_data for a worker (empty dict when absent)."""
        try:
            rec = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
        except Exception:
            return {}
        return (rec or {}).get("personalization_data") or {}

    def get_effective_gesture_mapping(
        self,
        worker_profile_id: UUID,
    ) -> Dict[str, Any]:
        """
        Build the effective gesture mapping + calibration for a worker.

        Returns a dict:
        {
          "gesture_action_map": {gesture: action, ...},
          "sources": {gesture: "worker_override"|"preset"|"default", ...},
          "calibration": {...merged calibration settings...},
          "worker_profile_id": str
        }
        """
        try:
            rec = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
        except Exception:
            rec = None
        preset_id = (rec or {}).get("interaction_configuration_id")

        preset_map = self._preset_mapping(preset_id)
        worker_map = self._worker_overrides(worker_profile_id)

        effective: Dict[str, str] = dict(DEFAULT_GESTURE_ACTION_MAP)
        sources: Dict[str, str] = {g: "default" for g in effective}
        for g, a in preset_map.items():
            effective[g] = a
            sources[g] = "preset"
        for g, a in worker_map.items():
            effective[g] = a
            sources[g] = "worker_override"

        raw = self.get_worker_raw_personalization(worker_profile_id)
        calibration = self._merged_calibration(raw)

        return {
            "worker_profile_id": str(worker_profile_id),
            "gesture_action_map": effective,
            "sources": sources,
            "calibration": calibration,
        }

    def _merged_calibration(self, raw_personalization: Dict[str, Any]) -> Dict[str, Any]:
        """Merge stored calibration over defaults; unknown keys preserved."""
        stored = raw_personalization.get("interaction_calibration")
        if not isinstance(stored, dict):
            stored = {}
        merged = dict(DEFAULT_CALIBRATION)
        enabled = dict(merged.get("enabled_gestures", {}))
        stored_enabled = stored.get("enabled_gestures")
        if isinstance(stored_enabled, dict):
            enabled.update({str(k): bool(v) for k, v in stored_enabled.items()})
        for key, value in stored.items():
            if key == "enabled_gestures":
                continue
            if key in merged and value is not None:
                merged[key] = value
        merged["enabled_gestures"] = enabled
        # Legacy top-level dwell_time_ms (used by earlier phases) still honored
        dwell = raw_personalization.get("dwell_time_ms")
        if isinstance(dwell, (int, float)) and "dwell_time_ms" not in stored:
            merged["dwell_time_ms"] = int(dwell)
        return merged

    def resolve_gesture_action(
        self,
        worker_profile_id: Optional[UUID],
        gesture_name: str,
    ) -> Optional[str]:
        """Resolve a single gesture to its action for a specific worker."""
        if not gesture_name:
            return None
        gesture = gesture_name.lower().strip()
        if gesture.startswith("custom_"):
            # Custom gesture intents carry their own action mapping suffix
            # (e.g. custom_confirm -> confirm_action) resolved by the custom
            # gesture pipeline itself.
            return None
        if worker_profile_id:
            overrides = self._worker_overrides(worker_profile_id)
            if gesture in overrides:
                return overrides[gesture]
        if worker_profile_id:
            try:
                rec = self.personalizations_repo.get_by_worker_profile_id(worker_profile_id)
            except Exception:
                rec = None
            preset_id = (rec or {}).get("interaction_configuration_id")
            preset_map = self._preset_mapping(preset_id)
            if gesture in preset_map:
                return preset_map[gesture]
        return DEFAULT_GESTURE_ACTION_MAP.get(gesture)

    # ------------------------------------------------------------------
    # Mapping persistence (worker-specific, PostgreSQL-authoritative)
    # ------------------------------------------------------------------

    def _validate_mapping(self, gesture_action_map: Dict[str, str]) -> List[str]:
        """Validate gesture names and action names. Returns list of errors."""
        errors: List[str] = []
        known_actions = self._known_action_names()
        for gesture, action in gesture_action_map.items():
            if not isinstance(gesture, str) or not gesture.strip():
                errors.append(f"Invalid gesture name '{gesture}'.")
                continue
            if not isinstance(action, str) or not action.strip():
                errors.append(f"Gesture '{gesture}' mapped to empty action.")
                continue
            if known_actions and action not in known_actions:
                errors.append(
                    f"Gesture '{gesture}' mapped to unknown action '{action}'."
                )
        return errors

    def update_worker_mapping(
        self,
        worker_profile_id: UUID,
        gesture_action_map: Optional[Dict[str, str]] = None,
        calibration: Optional[Dict[str, Any]] = None,
        change_reason: str = "Worker gesture mapping update",
    ) -> Dict[str, Any]:
        """
        Persist worker-specific gesture mapping overrides and calibration into
        worker_personalizations.personalization_data (with audit history).
        """
        current = self.get_worker_raw_personalization(worker_profile_id)
        new_data = dict(current)

        if gesture_action_map is not None:
            # Start from current overrides so partial updates merge cleanly
            merged_map = dict(current.get("gesture_action_map") or {})
            merged_map.update({str(k): str(v) for k, v in gesture_action_map.items()})
            errors = self._validate_mapping(merged_map)
            if errors:
                raise ValueError("; ".join(errors))
            new_data["gesture_action_map"] = merged_map

        if calibration is not None:
            if not isinstance(calibration, dict):
                raise ValueError("Calibration must be an object.")
            merged_cal = dict(current.get("interaction_calibration") or {})
            merged_cal.update(calibration)
            new_data["interaction_calibration"] = merged_cal

        updated = self.personalization_service.update_personalization(
            worker_profile_id=worker_profile_id,
            new_data=new_data,
            change_reason=change_reason,
        )
        return self.get_effective_gesture_mapping(worker_profile_id)
