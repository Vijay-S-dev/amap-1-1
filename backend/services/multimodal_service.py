"""
Multimodal Fusion and Cross-Modal Arbitration Service for AMAP.

Implements temporal window correlation, probabilistic confidence reinforcement,
complementary spatial-action binding, and safety-first conflict resolution rules.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from models.base import InteractionMode
from models.multimodal import (
    MultimodalFusionPayload,
    MultimodalFusionResult,
    MultimodalInputItem,
)
from services.gesture_service import GESTURE_ACTION_MAPPING
from services.interaction_service import INTENT_ACTION_MAP


SAFETY_CRITICAL_ACTIONS = {"emergency_stop", "cancel_action", "pause_session"}
MIN_CONFIDENCE_THRESHOLD = 0.40

REGISTERED_AMAP_ACTIONS = {
    "next_step",
    "confirm_action",
    "previous_step",
    "pause_session",
    "resume_session",
    "emergency_stop",
    "request_assistance",
    "cancel_action",
    # Real-time computer/UI interaction actions (migration 052)
    "pointer_move",
    "left_click",
    "right_click",
    "double_click",
    "drag_start",
    "drag_move",
    "drag_end",
    "scroll",
    "scroll_up",
    "scroll_down",
    "scroll_left",
    "scroll_right",
    "select_item",
    # Task lifecycle actions
    "start_assignment",
    "complete_step",
    "finish_assignment",
}

# Gesture poses whose action may target an on-screen element at the
# on-screen pointer position (spatial context binding).
SPATIAL_ACTIONS = {"point_focus", "select_item", "left_click", "right_click", "double_click", "drag_start"}

CANONICAL_VOICE_MAP = {
    "emergency_stop": "emergency_stop",
    "emergency stop": "emergency_stop",
    "emergency": "emergency_stop",
    "stop": "emergency_stop",
    "halt": "emergency_stop",
    "roko": "emergency_stop",
    "ruko": "emergency_stop",
    "estop": "emergency_stop",
    "next": "next_step",
    "next step": "next_step",
    "agla": "next_step",
    "continue": "next_step",
    "proceed": "next_step",
    "advance": "next_step",
    "previous": "previous_step",
    "previous step": "previous_step",
    "back": "previous_step",
    "pichla": "previous_step",
    "confirm": "confirm_action",
    "confirm action": "confirm_action",
    "confirm step": "confirm_action",
    "pushti": "confirm_action",
    "yes": "confirm_action",
    "ok": "confirm_action",
    "cancel": "cancel_action",
    "cancel action": "cancel_action",
    "pause": "pause_session",
    "pause session": "pause_session",
    "resume": "resume_session",
    "resume session": "resume_session",
    "help": "request_assistance",
    "madad": "request_assistance",
    "assistance": "request_assistance",
    "request assistance": "request_assistance",
    # --- Computer / UI interaction commands ---
    "left click": "left_click",
    "click": "left_click",
    "right click": "right_click",
    "double click": "double_click",
    "drag": "drag_start",
    "move this": "drag_start",
    "grab": "drag_start",
    "drop": "drag_end",
    "release": "drag_end",
    "select": "select_item",
    "scroll up": "scroll_up",
    "scroll down": "scroll_down",
    "scroll left": "scroll_left",
    "scroll right": "scroll_right",
    # --- Task lifecycle commands ---
    "start task": "start_assignment",
    "start assignment": "start_assignment",
    "start work": "start_assignment",
    "complete step": "complete_step",
    "finish task": "finish_assignment",
    "finish assignment": "finish_assignment",
    "end work": "finish_assignment",
}


def _resolve_candidate_action(
    item: MultimodalInputItem,
    worker_profile_id: Optional[UUID] = None,
    gesture_action_map: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], bool]:
    """
    Resolve raw intent and mode to a standardized AMAP candidate action.
    Returns (action_name, is_spatial_target).

    When a worker gesture_action_map is supplied (resolved by the route from
    PostgreSQL — personalization override -> org preset -> canonical default),
    gesture intents are resolved through it so personalized mappings apply to
    multimodal fusion exactly as they do to direct gesture recognition.
    """
    raw = item.raw_intent.lower().strip()

    # 1. Gesture Modality Mapping
    if item.mode == InteractionMode.GESTURE:
        # Emergency stop priority gesture
        if raw in {"fist", "closed_fist"}:
            return "emergency_stop", False

        # Pointing gesture: check if spatial target context is present
        if raw in {"pointing", "point"}:
            spatial_keys = {"target_part_id", "spatial_x", "spatial_y", "coordinates", "target_id"}
            if any(k in item.context_data for k in spatial_keys):
                return "point_focus", True
            return "next_step", False

        # Worker-personalized mapping takes precedence for standard gestures
        # (excluding the safety-priority fist above).
        if gesture_action_map and raw in gesture_action_map:
            action = gesture_action_map[raw]
            return action, action in SPATIAL_ACTIONS

        # Thumbs up / down
        if raw == "thumbs_up":
            return "confirm_action", False
        if raw == "thumbs_down":
            return "cancel_action", False

        # Open palm / pause
        if raw in {"open_palm", "palm"}:
            return "pause_session", False

        # Pinch / swipe
        if raw == "pinch":
            return "left_click", True
        if raw == "pinch_hold":
            return "select_item", True
        if raw == "two_finger":
            return "right_click", True
        if raw == "swipe_right":
            return "next_step", False
        if raw == "swipe_left":
            return "previous_step", False
        if raw == "swipe_up":
            return "scroll_up", False
        if raw == "swipe_down":
            return "scroll_down", False

        # Fallback to GESTURE_ACTION_MAPPING if present
        if raw in GESTURE_ACTION_MAPPING:
            action = GESTURE_ACTION_MAPPING[raw]
            is_spatial = action in SPATIAL_ACTIONS
            return action, is_spatial

        if raw == "unknown":
            return None, False

    # 2. Voice and General Intent Mapping
    if raw in CANONICAL_VOICE_MAP:
        action = CANONICAL_VOICE_MAP[raw]
        return action, action in SPATIAL_ACTIONS and item.mode == InteractionMode.GESTURE

    if raw in INTENT_ACTION_MAP:
        action = INTENT_ACTION_MAP[raw]
        is_spatial = action in SPATIAL_ACTIONS
        return action, is_spatial

    # Registered direct action name
    if raw in REGISTERED_AMAP_ACTIONS:
        return raw, raw in SPATIAL_ACTIONS and item.mode == InteractionMode.GESTURE

    # Unrecognized intent
    return None, False


class MultimodalService:
    """
    Orchestrates cross-modal intent fusion and conflict disambiguation.
    Enforces invariant: Recognition != Intent != Authorization != Execution.
    Never executes actions or mutates the database directly.
    """

    def fuse_inputs(
        self,
        payload: MultimodalFusionPayload,
        worker_profile_id: Optional[UUID] = None,
        gesture_action_map: Optional[Dict[str, str]] = None,
    ) -> MultimodalFusionResult:
        """
        Arbitrate multi-modal inputs within the specified temporal window.

        gesture_action_map is the worker's effective gesture mapping resolved
        by the caller (route layer) from PostgreSQL; the fusion service itself
        stays a pure computation over its inputs (no database access).
        """
        inputs = payload.inputs
        if not inputs:
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=0.0,
                fusion_strategy="single_mode",
                requires_confirmation=False,
                contributing_modes=[],
                validation_status="rejected",
                message="No inputs provided for multimodal fusion.",
            )

        # 1. Check for inputs meeting the minimum confidence threshold
        confident_items = [item for item in inputs if item.confidence >= MIN_CONFIDENCE_THRESHOLD]
        if not confident_items:
            max_c = round(max(item.confidence for item in inputs), 3)
            all_modes = list({str(item.mode.value if hasattr(item.mode, "value") else item.mode) for item in inputs})
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=max_c,
                fusion_strategy="low_confidence_rejected",
                requires_confirmation=False,
                contributing_modes=all_modes,
                validation_status="rejected",
                message=f"Input confidence ({max_c}) below acceptable threshold ({MIN_CONFIDENCE_THRESHOLD}). Action rejected for safety.",
            )

        # 2. Temporal Window Filter: Filter out any items diverging > temporal_window_ms from the latest
        max_ts = max(item.timestamp_ms for item in confident_items)
        valid_items = [
            item for item in confident_items
            if (max_ts - item.timestamp_ms) <= payload.temporal_window_ms
        ]

        # Stale check: do NOT resurrect discarded stale items
        if not valid_items:
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=0.0,
                fusion_strategy="stale_rejected",
                requires_confirmation=False,
                contributing_modes=[],
                validation_status="rejected",
                message="Multimodal inputs exceeded temporal divergence window and were discarded as stale.",
            )

        # 3. Case: Single Modality Input
        if len(valid_items) == 1:
            item = valid_items[0]
            action, _ = _resolve_candidate_action(item, worker_profile_id, gesture_action_map)
            mode_str = str(item.mode.value if hasattr(item.mode, "value") else item.mode)

            if action is None:
                return MultimodalFusionResult(
                    fused_action=None,
                    fused_confidence=item.confidence,
                    fusion_strategy="single_mode",
                    requires_confirmation=False,
                    contributing_modes=[mode_str],
                    target_context={},
                    validation_status="rejected",
                    message=f"Unrecognized {mode_str} input '{item.raw_intent}'.",
                )

            is_critical = action in SAFETY_CRITICAL_ACTIONS
            return MultimodalFusionResult(
                fused_action=action,
                fused_confidence=item.confidence,
                fusion_strategy="single_mode",
                requires_confirmation=is_critical,
                contributing_modes=[mode_str],
                target_context=item.context_data,
                validation_status="valid",
                message=f"Single modality intent '{action}' processed.",
            )

        # 4. Emergency Stop Priority Check (Fail-Safe across ALL modalities in multi-input bundle)
        for item in valid_items:
            act, _ = _resolve_candidate_action(item, worker_profile_id, gesture_action_map)
            if act == "emergency_stop":
                estop_conf = max(
                    itm.confidence for itm in valid_items
                    if _resolve_candidate_action(itm, worker_profile_id, gesture_action_map)[0] == "emergency_stop"
                )
                all_modes = list({str(itm.mode.value if hasattr(itm.mode, "value") else itm.mode) for itm in valid_items})
                return MultimodalFusionResult(
                    fused_action="emergency_stop",
                    fused_confidence=estop_conf,
                    fusion_strategy="conflict_resolved",
                    requires_confirmation=True,  # Safety-critical action flag
                    contributing_modes=all_modes,
                    target_context={},
                    validation_status="valid",
                    message="Emergency Stop safety override activated immediately across modalities.",
                )

        # 5. Analyze multi-modal candidate actions
        resolved_actions = []
        spatial_targets: Dict[str, Any] = {}
        contributing_modes = list({
            str(item.mode.value if hasattr(item.mode, "value") else item.mode)
            for item in valid_items
        })

        for item in valid_items:
            action, is_spatial = _resolve_candidate_action(item, worker_profile_id, gesture_action_map)
            if is_spatial and item.context_data:
                spatial_targets.update(item.context_data)
            resolved_actions.append((action, item.confidence, item))

        # Check distinct non-spatial actions
        distinct_actions = {a for a, _, _ in resolved_actions if a is not None}

        # If all items resolved to None / unknown
        if not distinct_actions:
            max_c = round(max(item.confidence for item in valid_items), 3)
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=max_c,
                fusion_strategy="single_mode",
                requires_confirmation=False,
                contributing_modes=contributing_modes,
                target_context={},
                validation_status="rejected",
                message="Unrecognized multimodal inputs.",
            )

        # 6. Case: Redundant / Reinforcing Fusion (all inputs agree on action)
        if len(distinct_actions) == 1:
            action = list(distinct_actions)[0]
            # Probabilistic reinforcement: 1 - product(1 - C_i)
            inv_product = 1.0
            for _, conf, _ in resolved_actions:
                inv_product *= (1.0 - conf)
            fused_conf = round(min(0.99, 1.0 - inv_product), 3)

            is_critical = action in SAFETY_CRITICAL_ACTIONS and action != "emergency_stop"
            merged_context: Dict[str, Any] = {}
            for _, _, itm in resolved_actions:
                merged_context.update(itm.context_data)

            return MultimodalFusionResult(
                fused_action=action,
                fused_confidence=fused_conf,
                fusion_strategy="reinforcing",
                requires_confirmation=is_critical,
                contributing_modes=contributing_modes,
                target_context=merged_context,
                validation_status="valid",
                message=f"Reinforcing multimodal agreement on action '{action}' (confidence boosted to {fused_conf}).",
            )

        # 6b. Direction refinement rule: a generic parameterized action (e.g.
        # two-finger "scroll" movement) refined by a modality-specific
        # directional command (e.g. voice "scroll down") fuses onto the
        # specific action. Gesture supplies the modality; voice supplies the
        # direction — controlled scrolling instead of an ambiguous conflict.
        SCROLL_ACTIONS = {"scroll_up", "scroll_down", "scroll_left", "scroll_right"}
        if (
            "scroll" in distinct_actions
            and len(distinct_actions) == 2
            and (distinct_actions - {"scroll"}).issubset(SCROLL_ACTIONS)
        ):
            specific = next(a for a in distinct_actions if a != "scroll")
            specific_conf = max(c for a, c, _ in resolved_actions if a == specific)
            generic_conf = max(c for a, c, _ in resolved_actions if a == "scroll")
            merged_ctx: Dict[str, Any] = {}
            for _, _, itm in resolved_actions:
                merged_ctx.update(itm.context_data)
            return MultimodalFusionResult(
                fused_action=specific,
                fused_confidence=round(min(0.99, max(specific_conf, generic_conf) + 0.02), 3),
                fusion_strategy="direction_refined",
                requires_confirmation=False,
                contributing_modes=contributing_modes,
                target_context=merged_ctx,
                validation_status="valid",
                message=f"Direction refinement: gesture scroll movement fused with '{specific}'.",
            )

        # 7. Case: Complementary Fusion (spatial carrier + operational action)
        # A "spatial carrier" is a GESTURE input that either resolved to a
        # pure spatial action (point_focus) or carries explicit spatial
        # coordinates (on-screen pointer position) in its context. The other
        # modality supplies the operational command which is then executed at
        # that spatial target (e.g. hand over element + "select", pinch at
        # element + "move this" -> drag at that position).
        def _is_spatial_carrier(action_name: Optional[str], itm: MultimodalInputItem) -> bool:
            if itm.mode != InteractionMode.GESTURE:
                return False
            if action_name == "point_focus":
                return True
            spatial_keys = {"target_part_id", "spatial_x", "spatial_y", "coordinates", "target_id"}
            return any(k in itm.context_data for k in spatial_keys)

        spatial_items = [
            (a, c, itm) for a, c, itm in resolved_actions
            if a is not None and _is_spatial_carrier(a, itm)
        ]
        action_items = [
            (a, c, itm) for a, c, itm in resolved_actions
            if a is not None and not _is_spatial_carrier(a, itm)
        ]

        if spatial_items and action_items:
            # Operational command bound to target
            primary_action, action_conf, act_itm = action_items[0]
            _, spatial_conf, spat_itm = spatial_items[0]

            fused_conf = round(math.sqrt(action_conf * spatial_conf), 3)
            merged_context = dict(spat_itm.context_data)
            merged_context.update(act_itm.context_data)

            is_critical = primary_action in SAFETY_CRITICAL_ACTIONS and primary_action != "emergency_stop"
            return MultimodalFusionResult(
                fused_action=primary_action,
                fused_confidence=fused_conf,
                fusion_strategy="complementary",
                requires_confirmation=is_critical,
                contributing_modes=contributing_modes,
                target_context=merged_context,
                validation_status="valid",
                message=f"Complementary multimodal binding: action '{primary_action}' focused on target.",
            )

        # 8. Case: Cross-Modal Conflict Resolution
        # Safety rule: Any safety-critical negative intent (e.g. cancel_action, pause_session) overrides positive intent
        critical_conflicts = [a for a in distinct_actions if a in SAFETY_CRITICAL_ACTIONS and a != "emergency_stop"]
        if critical_conflicts:
            crit_action = critical_conflicts[0]
            crit_conf = max(c for a, c, _ in resolved_actions if a == crit_action)
            return MultimodalFusionResult(
                fused_action=crit_action,
                fused_confidence=crit_conf,
                fusion_strategy="conflict_resolved",
                requires_confirmation=True,
                contributing_modes=contributing_modes,
                target_context={},
                validation_status="valid",
                message=f"Safety override: Critical action '{crit_action}' took precedence during cross-modal conflict.",
            )

        # General non-critical conflict (e.g. next_step vs previous_step)
        valid_resolved = [(a, c, itm) for a, c, itm in resolved_actions if a is not None]
        sorted_by_conf = sorted(valid_resolved, key=lambda x: x[1], reverse=True)
        top_action, top_conf, _ = sorted_by_conf[0]
        second_action, second_conf, _ = sorted_by_conf[1]

        if (top_conf - second_conf) >= 0.35:
            # Significant confidence margin -> select top candidate with confirmation
            return MultimodalFusionResult(
                fused_action=top_action,
                fused_confidence=top_conf,
                fusion_strategy="conflict_resolved",
                requires_confirmation=True,
                contributing_modes=contributing_modes,
                target_context={},
                validation_status="valid",
                message=f"Conflict resolved in favor of higher-confidence action '{top_action}'. Confirmation required.",
            )

        # Ambiguous conflict (close confidences, delta < 0.35)
        return MultimodalFusionResult(
            fused_action=None,
            fused_confidence=round((top_conf + second_conf) / 2.0, 3),
            fusion_strategy="conflict_ambiguous",
            requires_confirmation=True,
            contributing_modes=contributing_modes,
            target_context={},
            validation_status="ambiguous",
            message=f"Ambiguous cross-modal conflict between '{top_action}' and '{second_action}'. Disambiguation required.",
        )
