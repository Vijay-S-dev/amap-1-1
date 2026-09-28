"""
Voice pipeline domain schemas for AMAP.

Defines schemas for incoming transcribed voice audio commands and matched results.
"""

from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel


class VoiceCommandPayload(StrictInputModel):
    """
    Client payload representing a transcribed voice command from the worker interface.
    """
    raw_transcript: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Raw transcribed speech text",
    )
    confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Speech recognizer confidence score [0.0, 1.0]",
    )
    language: str = Field(default="en-US", max_length=20)
    work_session_id: Optional[str] = None
    client_context: Dict[str, Any] = Field(default_factory=dict)


class VoiceCommandResult(AMAPBaseModel):
    """
    Result of phonetic/fuzzy keyword matching and intent thresholding.
    """
    matched_command: Optional[str] = Field(
        None,
        description="Normalized command phrase (e.g. 'next_step', 'confirm_action')",
    )
    action_mapping: Optional[str] = Field(
        None,
        description="Target AMAP candidate action name",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Combined recognition and fuzzy similarity confidence score",
    )
    fuzzy_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="String similarity match score against vocabulary",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="True if confidence is moderate or action is safety-critical",
    )
    validation_status: str = Field(
        default="valid",
        description="Validation outcome: valid, low_confidence, or unmatched",
    )
    message: Optional[str] = None


class TranscriptionResult(AMAPBaseModel):
    """Result of a finalized streaming utterance (Vosk)."""

    transcript: str = Field(default="", max_length=2000)
    detected_language: str = Field(default="en", max_length=5)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(default=0.0, ge=0.0)
    success: bool = False


class STTHealthStatus(AMAPBaseModel):
    """Non-invasive health state for the lazy-loaded local STT model."""

    model_status: str
    model_name: str
    supported_languages: list[str]
