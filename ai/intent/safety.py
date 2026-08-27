"""
Safety Interlock & Authorization Gating Engine.

Enforces the AMAP core invariant:
    Recognition != Intent != Authorization != Execution
"""

from typing import Dict, List, Optional, Set, Tuple

from ai.config import SAFETY_CRITICAL_ACTIONS


class SafetyInterlockEvaluator:
    """
    Evaluates whether candidate actions require secondary interlocks,
    supervisor authorization, or physical machinery lockouts.
    """

    def __init__(self, critical_actions: Optional[Set[str]] = None) -> None:
        self.critical_actions = critical_actions or SAFETY_CRITICAL_ACTIONS

    def is_safety_critical(self, action: Optional[str]) -> bool:
        """Check if action is classified as safety critical."""
        if not action:
            return False
        return action.lower().strip() in self.critical_actions

    def evaluate_execution_gating(
        self,
        action: str,
        confidence: float,
        is_secondary_confirmed: bool = False,
        user_roles: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluate if an intended action is safe to dispatch to physical execution.
        Returns (is_permitted, reason).
        """
        norm_action = action.lower().strip()

        # 1. Emergency Stop is ALWAYS permissible to trigger immediately
        if norm_action == "emergency_stop":
            return True, "Emergency stop accepted immediately under fail-safe policy."

        # 2. Safety Critical Actions require secondary confirmation
        if norm_action in self.critical_actions:
            if not is_secondary_confirmed:
                return False, f"Action '{action}' is safety-critical and mandates explicit secondary confirmation."

        # 3. Low confidence check
        if confidence < 0.60:
            return False, f"Action confidence ({confidence:.2f}) is below minimum execution threshold (0.60)."

        # 4. Role-based privilege gating if specified
        if user_roles is not None:
            if norm_action in {"voltage_adjustment", "hydraulic_release", "station_shutdown"}:
                if "supervisor" not in user_roles and "admin" not in user_roles:
                    return False, f"Action '{action}' requires supervisor or admin role privilege."

        return True, "Action passed safety interlocks and is authorized for execution."
