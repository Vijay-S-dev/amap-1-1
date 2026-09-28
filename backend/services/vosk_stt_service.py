"""Vosk streaming speech-to-text service for AMAP.

Replaces the previous faster-whisper batch transcription service. AMAP has
exactly ONE speech-recognition engine: Vosk (offline, streaming).

Architecture (see VOSK_VOICE_FEASIBILITY_REPORT.md):

    Browser microphone
      -> WebSocket PCM frames
      -> VoskModelRegistry (models loaded once per process)
      -> VoiceStreamSession (isolated per-connection KaldiRecognizer)
      -> Kaldi end-of-speech endpointer (in-model)   <- ONLY finalizer
      -> FINAL transcript
      -> existing VoiceService (command parser + safety validation)

Safety invariants enforced here:
- FREE-FORM recognition only. Grammar-constrained decoding is forbidden:
  the feasibility investigation measured that grammar mode force-maps
  out-of-vocabulary speech onto valid command phrases (e.g. "Open production
  quality" -> "up approve action call okay" -> confirm_action), which can
  cause unsafe false command matches.
- Partial results are display-only feedback; only endpointer-finalized
  utterances are emitted as final events.
- Each WebSocket connection owns an isolated recognizer; recognizer state is
  never shared between users/connections.
- No raw audio is persisted anywhere.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.voice import STTHealthStatus

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "hi")

# Deterministic model provisioning (scripts/prefetch_vosk_models.py installs
# exactly these versions into AMAP_VOSK_MODELS_DIR, default backend/.vosk_cache).
VOSK_MODEL_SPECS: Dict[str, Dict[str, str]] = {
    "en": {
        "directory": "vosk-model-small-en-us-0.15",
        "version": "0.15",
        "sha256": "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498",
        "size_bytes": 41205931,
        "source": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    },
    "hi": {
        "directory": "vosk-model-small-hi-0.22",
        "version": "0.22",
        # SHA-256 of the official zip (published checksum list, VocaHQ/vocalinux).
        "sha256": "7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48",
        "size_bytes": 44458845,
        "source": "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip",
    },
}

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent / ".vosk_cache"


class VoskModelUnavailableError(RuntimeError):
    """Raised when a required Vosk model is missing or failed to load."""


class VoskModelRegistry:
    """Loads the required Vosk models once per process and hands out isolated
    per-connection recognizers. Thread-safe; models are never reloaded per
    command or per connection."""

    _instance: Optional["VoskModelRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, models_dir: Optional[str] = None) -> "VoskModelRegistry":
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, models_dir: Optional[str] = None) -> None:
        if self._initialized:
            return
        self._models_dir = Path(models_dir or os.getenv("AMAP_VOSK_MODELS_DIR") or DEFAULT_MODELS_DIR)
        self._models: Dict[str, Any] = {}
        self._model_errors: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._preloading = False
        self._initialized = True

    # ------------------------------------------------------------------ state
    @property
    def models_dir(self) -> Path:
        return self._models_dir

    def model_path(self, language: str) -> Path:
        spec = VOSK_MODEL_SPECS.get(language)
        if spec is None:
            raise VoskModelUnavailableError(f"Unsupported language '{language}'")
        return self._models_dir / spec["directory"]

    def model_status(self, language: str) -> str:
        if language in self._models:
            return "READY"
        if language in self._model_errors:
            return "ERROR"
        return "NOT_INITIALIZED"

    def health(self) -> STTHealthStatus:
        statuses = [self.model_status(lang) for lang in SUPPORTED_LANGUAGES]
        if all(s == "READY" for s in statuses):
            overall = "READY"
        elif any(s == "ERROR" for s in statuses):
            overall = "ERROR"
        else:
            overall = "NOT_INITIALIZED"
        names = "+".join(
            f"vosk-model-small-{'en-us' if lang == 'en' else 'hi'}-{VOSK_MODEL_SPECS[lang]['version']}"
            for lang in SUPPORTED_LANGUAGES
        )
        return STTHealthStatus(
            model_status=overall,
            model_name=names,
            supported_languages=list(SUPPORTED_LANGUAGES),
        )

    # ------------------------------------------------------------------ load
    def preload(self) -> None:
        """Load every required model exactly once (idempotent, thread-safe)."""
        for language in SUPPORTED_LANGUAGES:
            self.get_model(language)

    def get_model(self, language: str) -> Any:
        normalized = (language or "").strip().lower().split("-")[0]
        if normalized not in SUPPORTED_LANGUAGES:
            raise VoskModelUnavailableError(
                f"Only English (en) and Hindi (hi) are supported, got '{language}'"
            )
        if normalized in self._models:
            return self._models[normalized]
        with self._lock:
            if normalized in self._models:
                return self._models[normalized]
            path = self.model_path(normalized)
            if not (path / "conf").is_dir() and not (path / "am").is_dir():
                self._model_errors[normalized] = (
                    f"Vosk model directory missing: {path}. "
                    "Run scripts/prefetch_vosk_models.py to provision the models."
                )
                logger.error(self._model_errors[normalized])
                raise VoskModelUnavailableError(self._model_errors[normalized])
            try:
                from vosk import Model  # imported lazily so non-voice tests stay fast

                started = time.perf_counter()
                model = Model(str(path))
                self._models[normalized] = model
                self._model_errors.pop(normalized, None)
                logger.info(
                    "Loaded Vosk model '%s' for '%s' in %.2fs",
                    path.name, normalized, time.perf_counter() - started,
                )
                return model
            except VoskModelUnavailableError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._model_errors[normalized] = f"Vosk model '{path}' failed to load: {exc}"
                logger.exception("Unable to load Vosk model for '%s'", normalized)
                raise VoskModelUnavailableError(self._model_errors[normalized]) from exc

    # ------------------------------------------------------------- sessions
    def new_session(self, language: str, sample_rate: int = 16000) -> "VoiceStreamSession":
        """Create an ISOLATED recognition session for one WebSocket connection."""
        model = self.get_model(language)
        return VoiceStreamSession(model=model, language=language, sample_rate=sample_rate)

    @classmethod
    def reset_for_tests(cls) -> None:
        """Drop the singleton (tests only) so the next construction is fresh
        and honors a custom models_dir."""
        with cls._instance_lock:
            cls._instance = None


def get_vosk_registry() -> VoskModelRegistry:
    """FastAPI dependency provider (singleton)."""
    return VoskModelRegistry()


class VoiceStreamSession:
    """Isolated per-connection streaming recognizer (free-form, endpointer-driven).

    One session == one WebSocket connection == one KaldiRecognizer. Session
    state (partial hypothesis, decoder state) is never shared across users.

    Usage:
        session = registry.new_session("en")
        for pcm_chunk in audio_chunks:            # 16-bit LE mono PCM bytes
            event = session.feed(pcm_chunk)       # {"type": "partial"|"final"}
            if event["type"] == "final": ...      # ONLY finals may be executed

    The Kaldi endpointer embedded in the model (silence-phone rules in
    model.conf) is the ONLY utterance finalizer: `feed` returns a final event
    exactly when Vosk's AcceptWaveform signals end-of-speech, and re-arms
    automatically for the next utterance. No external VAD, no client stop
    signal, no recording cap.
    """

    def __init__(self, model: Any, language: str, sample_rate: int = 16000) -> None:
        from vosk import KaldiRecognizer, SetLogLevel

        # Keep Kaldi's own logs out of request logs; service logs its own lines.
        SetLogLevel(-1)
        self._recognizer = KaldiRecognizer(model, sample_rate)
        self._recognizer.SetWords(True)
        self._language = language
        self._sample_rate = sample_rate
        self._last_partial: str = ""
        self._partial_count = 0
        self._final_count = 0
        self._started_at = time.perf_counter()
        self._last_voice_at: Optional[float] = None

    @property
    def language(self) -> str:
        return self._language

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def final_count(self) -> int:
        return self._final_count

    @staticmethod
    def _validate_pcm(chunk: bytes) -> None:
        if not chunk:
            raise ValueError("Empty audio frame")
        if len(chunk) % 2 != 0:
            raise ValueError("Malformed audio frame: 16-bit PCM frames must have an even byte length")

    def feed(self, pcm_chunk: bytes) -> Optional[Dict[str, Any]]:
        """Feed one PCM chunk. Returns a partial/final event or None.

        Returns:
            {"type": "partial", "text": str}
            {"type": "final", "transcript": str, "confidence": float,
             "word_count": int, "processing_time_ms": float, "utterance": int}
        """
        self._validate_pcm(pcm_chunk)
        endpointed = self._recognizer.AcceptWaveform(pcm_chunk)
        if endpointed:
            return self._final_event()
        partial = self._partial_event()
        self._last_voice_at = time.perf_counter()
        return partial

    def _partial_event(self) -> Optional[Dict[str, Any]]:
        raw = json.loads(self._recognizer.PartialResult())
        text = (raw.get("partial") or "").strip()
        if not text or text == self._last_partial:
            return None
        self._last_partial = text
        self._partial_count += 1
        # Partials carry NO command payload: display-only by contract.
        return {"type": "partial", "text": text}

    def _final_event(self) -> Dict[str, Any]:
        raw = json.loads(self._recognizer.FinalResult())
        words: List[Dict[str, Any]] = raw.get("result") or []
        transcript = (raw.get("text") or "").strip()
        confidence = 0.0
        if words:
            confidence = round(sum(w.get("conf", 0.0) for w in words) / len(words), 4)
        self._final_count += 1
        self._last_partial = ""
        speech_end_s = words[-1].get("end") if words else None
        return {
            "type": "final",
            "transcript": transcript,
            "confidence": confidence,
            "word_count": len(words),
            "utterance": self._final_count,
            # End time of the last recognized word, in audio-stream seconds
            # (used for latency instrumentation: speech end -> final).
            "speech_end_s": speech_end_s,
            "processing_time_ms": round((time.perf_counter() - self._started_at) * 1000, 2),
        }

    def finish(self) -> Optional[Dict[str, Any]]:
        """Flush any trailing hypothesis when the client disconnects.

        Used only to report what was said before the socket closed; the
        result is a final transcript and follows the same safety path.
        """
        try:
            self._recognizer.AcceptWaveform(b"")
            event = self._final_event()
            return event if event.get("transcript") else None
        except Exception:  # noqa: BLE001
            return None
