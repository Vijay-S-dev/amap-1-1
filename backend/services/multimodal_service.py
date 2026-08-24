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


def _resolve_candidate_action(item: MultimodalInputItem) -> Tuple[Optional[str], bool]:
    """
    Resolve raw intent and mode to a standardized AMAP candidate action.
    Returns (action_name, is_spatial_target).
    """
    raw = item.raw_intent.lower().strip()

    # Check gesture mappings
    if item.mode == InteractionMode.GESTURE:
        if raw in GESTURE_ACTION_MAPPING:
            action = GESTURE_ACTION_MAPPING[raw]
            is_spatial = action in {"point_focus", "select_item"}
            return action, is_spatial

    # Check generalized intent map
    if raw in INTENT_ACTION_MAP:
        action = INTENT_ACTION_MAP[raw]
        is_spatial = action in {"point_focus", "select_item"}
        return action, is_spatial

    return raw, False


class MultimodalService:
    """
    Orchestrates cross-modal intent fusion and conflict disambiguation.
    """

    def fuse_inputs(
        self,
        payload: MultimodalFusionPayload,
        worker_profile_id: Optional[UUID] = None,
    ) -> MultimodalFusionResult:
        """
        Arbitrate multi-modal inputs within the specified temporal window.
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

        # 1. Temporal Window Filter: Filter out any items diverging > temporal_window_ms from the latest
        max_ts = max(item.timestamp_ms for item in inputs)
        valid_items = [
            item for item in inputs
            if (max_ts - item.timestamp_ms) <= payload.temporal_window_ms
        ]

        if not valid_items:
            valid_items = inputs

        # 2. Case: Single Modality Input
        if len(valid_items) == 1:
            item = valid_items[0]
            action, _ = _resolve_candidate_action(item)
            is_critical = action in SAFETY_CRITICAL_ACTIONS
            mode_str = str(item.mode.value if hasattr(item.mode, "value") else item.mode)
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

        # 3. Analyze multi-modal candidate actions
        resolved_actions = []
        spatial_targets: Dict[str, Any] = {}
        contributing_modes = list({
            str(item.mode.value if hasattr(item.mode, "value") else item.mode)
            for item in valid_items
        })

        for item in valid_items:
            action, is_spatial = _resolve_candidate_action(item)
            if is_spatial and item.context_data:
                spatial_targets.update(item.context_data)
            resolved_actions.append((action, item.confidence, item))

        # Check distinct non-spatial actions
        distinct_actions = {a for a, _, _ in resolved_actions if a is not None}

        # 4. Case: Redundant / Reinforcing Fusion (all inputs agree on action)
        if len(distinct_actions) == 1:
            action = list(distinct_actions)[0]
            # Probabilistic reinforcement: 1 - product(1 - C_i)
            inv_product = 1.0
            for _, conf, _ in resolved_actions:
                inv_product *= (1.0 - conf)
            fused_conf = round(min(0.99, 1.0 - inv_product), 3)

            is_critical = action in SAFETY_CRITICAL_ACTIONS
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

        # 5. Case: Complementary Fusion (spatial pointing + operational voice/UI action)
        spatial_items = [(a, c, itm) for a, c, itm in resolved_actions if a in {"point_focus", "select_item"}]
        action_items = [(a, c, itm) for a, c, itm in resolved_actions if a not in {"point_focus", "select_item"}]

        if spatial_items and action_items:
            # Operational command bound to target
            primary_action, action_conf, act_itm = action_items[0]
            _, spatial_conf, spat_itm = spatial_items[0]

            fused_conf = round(math.sqrt(action_conf * spatial_conf), 3)
            merged_context = dict(spat_itm.context_data)
            merged_context.update(act_itm.context_data)

            return MultimodalFusionResult(
                fused_action=primary_action,
                fused_confidence=fused_conf,
                fusion_strategy="complementary",
                requires_confirmation=primary_action in SAFETY_CRITICAL_ACTIONS,
                contributing_modes=contributing_modes,
                target_context=merged_context,
                validation_status="valid",
                message=f"Complementary multimodal binding: action '{primary_action}' focused on target.",
            )

        # 6. Case: Cross-Modal Conflict Resolution
        # Safety rule: Any safety-critical negative intent (e.g. emergency_stop, cancel_action) overrides positive intent
        critical_conflicts = [a for a in distinct_actions if a in SAFETY_CRITICAL_ACTIONS]
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

        # General conflict: Compare highest confidence vs second highest
        sorted_by_conf = sorted(resolved_actions, key=lambda x: x[1], reverse=True)
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

        # Ambiguous conflict (close confidences)
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
