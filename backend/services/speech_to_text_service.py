"""Local speech-to-text service backed by faster-whisper.

The model is intentionally lazy-loaded. Importing the API, running unit tests,
or checking health never downloads a model; the first transcription request
does that work once and all later requests reuse the same model instance.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from models.voice import STTHealthStatus, TranscriptionResult

logger = logging.getLogger(__name__)


class STTModelState(str, Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    LOADING = "LOADING"
    READY = "READY"
    ERROR = "ERROR"


SUPPORTED_LANGUAGES = ("en", "hi")
MODEL_NAME = "tiny"


@dataclass
class _AudioFile:
    path: str
    temporary: bool = True


class SpeechToTextService:
    """Thread-safe singleton-style service for local audio transcription."""

    _instance: Optional["SpeechToTextService"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "SpeechToTextService":
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._model: Any = None
        self._state = STTModelState.NOT_INITIALIZED
        self._error: Optional[str] = None
        self._model_lock = threading.Lock()
        self._initialized = True

    @property
    def state(self) -> STTModelState:
        return self._state

    def health(self) -> STTHealthStatus:
        return STTHealthStatus(
            model_status=self._state.value,
            model_name=f"faster-whisper-{MODEL_NAME}-cpu-int8",
            supported_languages=list(SUPPORTED_LANGUAGES),
        )

    @classmethod
    def reset_for_tests(cls) -> None:
        """Reset singleton state without downloading a model (tests only)."""
        with cls._instance_lock:
            cls._instance = None

    @staticmethod
    def validate_language(language: Optional[str]) -> Optional[str]:
        if language is None or not language.strip():
            return None
        normalized = language.strip().lower().replace("_", "-")
        normalized = normalized.split("-", 1)[0]
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("Only English (en) and Hindi (hi) are supported")
        return normalized

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is not None:
                return self._model
            self._state = STTModelState.LOADING
            self._error = None
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    MODEL_NAME,
                    device="cpu",
                    compute_type="int8",
                )
                self._state = STTModelState.READY
            except Exception as exc:
                self._state = STTModelState.ERROR
                self._error = str(exc)
                logger.exception("Unable to initialize faster-whisper")
                raise RuntimeError(
                    "Speech-to-text model could not be loaded. "
                    "Check faster-whisper installation and network access for the first download."
                ) from exc
        return self._model

    @staticmethod
    def _audio_to_wav(audio_bytes: bytes, filename: Optional[str]) -> _AudioFile:
        if not audio_bytes:
            raise ValueError("Audio payload is empty")

        suffix = Path(filename or "audio.webm").suffix.lower()
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise ValueError(
                "FFmpeg executable was not found on the backend PATH. "
                "Install FFmpeg and restart the backend."
            )

        input_path: Optional[str] = None
        wav_path: Optional[str] = None
        conversion_succeeded = False
        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix or ".webm", delete=False
            ) as temp:
                input_path = temp.name
                temp.write(audio_bytes)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
                wav_path = temp.name

            completed = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    input_path,
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    wav_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or "").strip()
                raise ValueError(
                    "Audio could not be decoded by FFmpeg"
                    + (f": {detail}" if detail else ".")
                )
            if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
                raise ValueError("FFmpeg produced an empty WAV file.")

            conversion_succeeded = True
            return _AudioFile(wav_path)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("FFmpeg audio conversion timed out.") from exc
        except OSError as exc:
            raise ValueError("FFmpeg could not be executed.") from exc
        finally:
            if input_path:
                try:
                    os.unlink(input_path)
                except OSError:
                    pass
            if wav_path and not conversion_succeeded:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    @staticmethod
    def _confidence(segments: list[Any]) -> float:
        values = []
        for segment in segments:
            avg_logprob = getattr(segment, "avg_logprob", None)
            if avg_logprob is not None:
                # Normalized confidence heuristic derived from Whisper log probability.
                # (Not a calibrated probability, but a bounded [0.0, 1.0] score).
                prob = math.exp(float(avg_logprob))
                values.append(max(0.0, min(1.0, prob)))
        return sum(values) / len(values) if values else 0.0

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> TranscriptionResult:
        started = time.perf_counter()
        normalized_requested_lang = self.validate_language(language)
        audio_file: Optional[_AudioFile] = None
        try:
            audio_file = self._audio_to_wav(audio_bytes, filename)
            model = self._load_model()
            segments_iter, info = model.transcribe(
                audio_file.path,
                language=normalized_requested_lang if language else None,
                vad_filter=True,
                beam_size=1,
            )
            segments = list(segments_iter)
            raw_info_lang = getattr(info, "language", None)
            info_language = raw_info_lang.lower().split("-")[0] if raw_info_lang else (normalized_requested_lang or "en")

            # Language validation with conditional Urdu→Hindi tolerance:
            # Only accept "ur" as "hi" when the user EXPLICITLY requested Hindi.
            # Auto-detection must NOT silently relabel genuine Urdu as Hindi.
            if info_language not in SUPPORTED_LANGUAGES:
                if info_language == "ur" and normalized_requested_lang == "hi":
                    # Spoken Hindustani: Whisper can't distinguish Hindi from Urdu
                    # on short clips. The user explicitly chose Hindi, so accept it.
                    info_language = "hi"
                elif normalized_requested_lang and normalized_requested_lang in SUPPORTED_LANGUAGES:
                    # Whisper's 30-second window heuristic is unreliable on 1-2 second clips.
                    # Trust the user's explicit language selection over auto-detection.
                    info_language = normalized_requested_lang
                else:
                    return TranscriptionResult(
                        transcript="",
                        detected_language=info_language,
                        confidence=0.0,
                        processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
                        success=False,
                    )

            transcript = " ".join(
                getattr(segment, "text", "").strip() for segment in segments
            ).strip()
            return TranscriptionResult(
                transcript=transcript,
                detected_language=info_language,
                confidence=self._confidence(segments),
                processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
                success=bool(transcript),
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Speech transcription failed")
            raise RuntimeError("Speech transcription failed") from exc
        finally:
            if audio_file and audio_file.temporary:
                try:
                    os.unlink(audio_file.path)
                except OSError:
                    logger.warning("Unable to remove temporary audio file %s", audio_file.path)
