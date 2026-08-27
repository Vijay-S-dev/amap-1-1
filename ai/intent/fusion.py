r"""
Cross-Modal Temporal Fusion and Multi-Signal Arbitration Engine.

Fuses optical gesture coordinates and acoustic speech tokens across an adjustable
temporal fusion window ($\Delta t \in [500ms, 2500ms]$).
Enforces probabilistic reinforcement:
    c_fused = 1 - (1 - c_gesture) * (1 - c_voice)
"""

import math
from typing import List, Optional, Tuple

from ai.config import (
    DEFAULT_TEMPORAL_WINDOW_MS,
    FUSED_CONFIDENCE_THRESHOLD_AUTO_EXEC,
    GESTURE_TO_ACTION,
    INTENT_ALIASES,
    SAFETY_CRITICAL_ACTIONS,
)
from ai.models.types import (
    FusionStrategy,
    InputModality,
    MultimodalFusionResult,
    MultimodalInputItem,
)


class CrossModalFusionEngine:
    """
    Arbitrates multi-modal input streams within a temporal correlation window.
    """

    def __init__(
        self,
        default_window_ms: int = DEFAULT_TEMPORAL_WINDOW_MS,
        auto_exec_threshold: float = FUSED_CONFIDENCE_THRESHOLD_AUTO_EXEC,
    ) -> None:
        self.default_window_ms = default_window_ms
        self.auto_exec_threshold = auto_exec_threshold

    def _normalize_action(self, item: MultimodalInputItem) -> Tuple[Optional[str], bool]:
        """
        Map raw intent string and modality to normalized AMAP action.
        Returns (action_name, is_spatial).
        """
        raw = item.raw_intent.lower().strip()

        # Direct gesture lookup
        if item.mode == InputModality.GESTURE and raw in GESTURE_TO_ACTION:
            action = GESTURE_TO_ACTION[raw]
            is_spatial = action in {"point_focus", "select_item"}
            return action, is_spatial

        # Intent aliases lookup
        if raw in INTENT_ALIASES:
            action = INTENT_ALIASES[raw]
            is_spatial = action in {"point_focus", "select_item"}
            return action, is_spatial

        return raw, False

    def fuse(
        self,
        inputs: List[MultimodalInputItem],
        temporal_window_ms: Optional[int] = None,
    ) -> MultimodalFusionResult:
        """
        Perform temporal fusion and cross-modal arbitration on input stream list.
        """
        if not inputs:
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=0.0,
                fusion_strategy=FusionStrategy.SINGLE_MODE,
                requires_confirmation=False,
                contributing_modes=[],
                validation_status="rejected",
                message="No input signals provided for fusion.",
            )

        window_ms = temporal_window_ms or self.default_window_ms

        # 1. Temporal Window Filtering
        timestamps = [item.timestamp_ms for item in inputs]
        t_min, t_max = min(timestamps), max(timestamps)
        time_spread = t_max - t_min

        if time_spread > window_ms and len(inputs) > 1:
            # Drop stale inputs outside window
            valid_inputs = [i for i in inputs if t_max - i.timestamp_ms <= window_ms]
            if not valid_inputs:
                valid_inputs = [inputs[-1]]
            inputs = valid_inputs

        # 2. Single Modality
        if len(inputs) == 1:
            item = inputs[0]
            action, is_spatial = self._normalize_action(item)
            is_critical = action in SAFETY_CRITICAL_ACTIONS

            return MultimodalFusionResult(
                fused_action=action,
                fused_confidence=round(item.confidence, 3),
                fusion_strategy=FusionStrategy.SINGLE_MODE,
                requires_confirmation=is_critical or (item.confidence < 0.70),
                contributing_modes=[item.mode],
                spatial_target_id=item.spatial_target,
                validation_status="valid",
                message=f"Single-mode {item.mode.value} action: {action}",
            )

        # 3. Multi-Signal Partitioning
        gesture_items = [i for i in inputs if i.mode == InputModality.GESTURE]
        voice_items = [i for i in inputs if i.mode == InputModality.VOICE]
        other_items = [i for i in inputs if i.mode not in (InputModality.GESTURE, InputModality.VOICE)]

        g_item = gesture_items[-1] if gesture_items else None
        v_item = voice_items[-1] if voice_items else None

        g_action, g_is_spatial = self._normalize_action(g_item) if g_item else (None, False)
        v_action, _ = self._normalize_action(v_item) if v_item else (None, False)

        # 4. Complementary Spatial-Action Binding (e.g. Gesture: point_focus / select_item + Voice: confirm / next)
        if g_is_spatial and v_item is not None:
            spatial_target = g_item.spatial_target or "target_element"
            combined_conf = round(1.0 - (1.0 - g_item.confidence) * (1.0 - v_item.confidence), 3)
            is_critical = v_action in SAFETY_CRITICAL_ACTIONS

            return MultimodalFusionResult(
                fused_action=v_action,
                fused_confidence=combined_conf,
                fusion_strategy=FusionStrategy.SPATIAL_COMPLEMENTARY,
                requires_confirmation=is_critical,
                contributing_modes=[InputModality.GESTURE, InputModality.VOICE],
                spatial_target_id=spatial_target,
                validation_status="valid",
                message=f"Spatial binding: {g_action} on [{spatial_target}] confirmed by voice {v_action}",
            )

        # 5. Reinforcing Strategy (Gesture and Voice agree on identical action)
        if g_action and v_action and (g_action == v_action):
            fused_conf = round(1.0 - (1.0 - g_item.confidence) * (1.0 - v_item.confidence), 3)
            is_critical = g_action in SAFETY_CRITICAL_ACTIONS

            return MultimodalFusionResult(
                fused_action=g_action,
                fused_confidence=fused_conf,
                fusion_strategy=FusionStrategy.REINFORCING,
                requires_confirmation=is_critical,
                contributing_modes=[InputModality.GESTURE, InputModality.VOICE],
                spatial_target_id=g_item.spatial_target or v_item.spatial_target,
                validation_status="valid",
                message=f"Reinforcing agreement on {g_action} (Fused confidence: {fused_conf:.3f})",
            )

        # 6. Conflicting Strategy (Inputs disagree)
        if g_action and v_action and (g_action != v_action):
            # Check for Safety Critical priority (e.g. Emergency stop or Cancel takes precedence)
            if "emergency_stop" in (g_action, v_action):
                return MultimodalFusionResult(
                    fused_action="emergency_stop",
                    fused_confidence=1.0,
                    fusion_strategy=FusionStrategy.SAFETY_INTERLOCKED,
                    requires_confirmation=True,
                    contributing_modes=[InputModality.GESTURE, InputModality.VOICE],
                    validation_status="safety_override",
                    message="Emergency stop override triggered amidst conflicting inputs.",
                )

            # Confidence differential arbitration
            diff = abs(g_item.confidence - v_item.confidence)
            if diff >= 0.25:
                # Strong leader
                winner_item = g_item if g_item.confidence > v_item.confidence else v_item
                winner_action = g_action if winner_item == g_item else v_action
                is_critical = winner_action in SAFETY_CRITICAL_ACTIONS

                return MultimodalFusionResult(
                    fused_action=winner_action,
                    fused_confidence=round(winner_item.confidence * 0.90, 3),  # slight penalty
                    fusion_strategy=FusionStrategy.CONFLICT_ARBITRATED,
                    requires_confirmation=is_critical or True,  # Disambiguation advised
                    contributing_modes=[winner_item.mode],
                    spatial_target_id=winner_item.spatial_target,
                    validation_status="valid",
                    message=f"Conflict resolved by confidence differential: {winner_action} won over alternative",
                )

            # Ambiguous conflict -> Mandate clarification
            return MultimodalFusionResult(
                fused_action=None,
                fused_confidence=0.0,
                fusion_strategy=FusionStrategy.CONFLICT_ARBITRATED,
                requires_confirmation=True,
                contributing_modes=[InputModality.GESTURE, InputModality.VOICE],
                validation_status="conflict_unresolved",
                message=f"Conflicting inputs: Gesture '{g_action}' ({g_item.confidence:.2f}) vs Voice '{v_action}' ({v_item.confidence:.2f}). Disambiguation required.",
            )

        # Fallback to most confident input
        best_input = max(inputs, key=lambda x: x.confidence)
        action, _ = self._normalize_action(best_input)
        return MultimodalFusionResult(
            fused_action=action,
            fused_confidence=best_input.confidence,
            fusion_strategy=FusionStrategy.SINGLE_MODE,
            requires_confirmation=action in SAFETY_CRITICAL_ACTIONS,
            contributing_modes=[best_input.mode],
            spatial_target_id=best_input.spatial_target,
            validation_status="valid",
            message=f"Selected highest confidence mode {best_input.mode.value}",
        )
