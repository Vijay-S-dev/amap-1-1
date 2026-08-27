"""
Contextual AI Assistant for Worker Guidance and Admin Workflow Synthesis.
"""

from typing import Any, Dict, List, Optional
import json
import re


class AIAssistant:
    """
    Contextual AI assistant for worker step guidance, accessible error explanation,
    and natural language administrative task decomposition.
    """

    def explain_task_step(
        self,
        step_title: str,
        step_description: str,
        accessibility_level: str = "standard",
    ) -> Dict[str, Any]:
        """
        Generate accessible, clear step-by-step guidance for workers with cognitive/sensory diversities.
        """
        simplified_instructions = [
            f"1. Check your workstation for {step_title}.",
            f"2. {step_description}",
            "3. Use thumbs-up gesture or say 'confirm' when finished.",
        ]

        if accessibility_level == "simplified":
            return {
                "headline": f"Current Step: {step_title}",
                "bullet_points": simplified_instructions,
                "recommended_gesture": "thumbs_up",
                "recommended_voice": "confirm",
                "visual_cue": "Look for the green highlighted bounding box on your HUD.",
            }

        return {
            "headline": step_title,
            "description": step_description,
            "instructions": simplified_instructions,
            "shortcuts": ["Thumbs Up (Confirm)", "Open Palm (Pause)", "Say 'Help' (Call Supervisor)"],
        }

    def explain_error(self, error_code: str, raw_message: str) -> str:
        """
        Translate technical errors into worker-friendly, non-intrusive guidance.
        """
        error_map = {
            "MISSED_GESTURE": "Your hand moved out of camera view. Keep your hand inside the frame and hold for 0.5s.",
            "LOW_AUDIO_SNR": "Background factory noise is loud. Try speaking closer to the mic or use hand gestures.",
            "CONFLICT_INPUT": "The system heard one command and saw another. Please confirm your choice on screen.",
            "SAFETY_INTERLOCK": "This action requires secondary approval. Please verify before continuing.",
        }
        return error_map.get(error_code, f"Note: {raw_message}. Feel free to use the help button if needed.")

    def generate_workflow_proposal(self, natural_language_spec: str) -> Dict[str, Any]:
        """
        Convert unstructured admin work descriptions into structured task and workflow steps.
        """
        lines = [line.strip() for line in natural_language_spec.strip().split("\n") if line.strip()]
        steps: List[Dict[str, Any]] = []

        for i, line in enumerate(lines, start=1):
            # Clean up numbers like "1. Assemble bracket"
            cleaned_title = re.sub(r"^\d+[\.\)]\s*", "", line)
            steps.append({
                "step_order": i,
                "title": cleaned_title,
                "instruction": f"Execute {cleaned_title.lower()} according to standard assembly protocol.",
                "suggested_gestures": ["thumbs_up", "point_focus"],
                "suggested_voice_phrases": ["next", "confirm"],
                "is_safety_critical": any(w in cleaned_title.lower() for w in ["voltage", "cut", "press", "hazard", "stop"]),
            })

        if not steps:
            steps = [
                {
                    "step_order": 1,
                    "title": "Initial Inspection",
                    "instruction": "Verify component orientation.",
                    "suggested_gestures": ["thumbs_up"],
                    "suggested_voice_phrases": ["confirm"],
                    "is_safety_critical": False,
                }
            ]

        return {
            "workflow_name": "Proposed Assembly Flow",
            "total_steps": len(steps),
            "steps": steps,
            "ai_confidence": 0.92,
        }
