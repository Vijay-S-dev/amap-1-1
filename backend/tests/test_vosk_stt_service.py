"""Unit coverage for the Vosk model registry (AMAP's only STT engine).

Model-independent behavior (singleton, language gate, missing-model failure
path) runs everywhere. Real-model tests are skipped when the models are not
provisioned (``python scripts/prefetch_vosk_models.py``).
"""

from pathlib import Path

import pytest

from services.vosk_stt_service import (
    SUPPORTED_LANGUAGES,
    VOSK_MODEL_SPECS,
    VoskModelRegistry,
    VoskModelUnavailableError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_PRESENT = all(
    (REPO_ROOT / "backend" / ".vosk_cache" / spec["directory"]).is_dir()
    for spec in VOSK_MODEL_SPECS.values()
)


@pytest.fixture(autouse=True)
def reset_registry():
    VoskModelRegistry.reset_for_tests()
    yield
    VoskModelRegistry.reset_for_tests()


def test_registry_is_singleton():
    first = VoskModelRegistry(models_dir="/tmp/does-not-matter")
    second = VoskModelRegistry(models_dir="/tmp/also-does-not-matter")
    assert first is second


def test_health_shape_and_supported_languages():
    registry = VoskModelRegistry(models_dir="/tmp/does-not-matter")
    health = registry.health()
    assert health.supported_languages == ["en", "hi"]
    assert tuple(SUPPORTED_LANGUAGES) == ("en", "hi")
    assert "vosk-model-small-en-us-0.15" in health.model_name
    assert "vosk-model-small-hi-0.22" in health.model_name


def test_unsupported_language_raises():
    registry = VoskModelRegistry(models_dir="/tmp/does-not-matter")
    for bad in ("fr", "de", "zh", "", None):
        with pytest.raises(VoskModelUnavailableError):
            registry.new_session(bad)


def test_language_normalization():
    """Locale tags normalize to the base language (en-US -> en, hi-IN -> hi);
    unsupported languages are rejected regardless of suffix."""
    registry = VoskModelRegistry(models_dir="/tmp/does-not-matter")
    with pytest.raises(VoskModelUnavailableError, match="Only English"):
        registry.new_session("fr-FR")
    # en-US passes the language gate and reaches model resolution, which
    # fails with the missing-model error for this bogus models dir.
    with pytest.raises(VoskModelUnavailableError, match="prefetch_vosk_models"):
        registry.new_session("en-US")


def test_missing_model_dir_is_reported_not_crashed():
    """A missing model must surface a clear unavailable error + ERROR health."""
    registry = VoskModelRegistry(models_dir=str(REPO_ROOT / "backend" / ".vosk_cache"))
    # Point at a directory that definitely has no models inside.
    bogus = REPO_ROOT / "backend" / "tests" / "fixtures"
    registry._models_dir = bogus
    with pytest.raises(VoskModelUnavailableError, match="prefetch_vosk_models"):
        registry.new_session("en")
    assert registry.health().model_status == "ERROR"


def test_model_specs_are_fully_pinned():
    """Deterministic provisioning: every model has source, checksum and size."""
    for language, spec in VOSK_MODEL_SPECS.items():
        assert spec["directory"].startswith("vosk-model-small-"), spec
        assert len(spec["sha256"]) == 64
        assert spec["size_bytes"] > 10_000_000
        assert spec["source"].startswith("https://")


@pytest.mark.skipif(not MODELS_PRESENT, reason="Vosk models not provisioned")
class TestRealModels:
    def test_preload_loads_both_models_once_and_health_ready(self):
        registry = VoskModelRegistry()
        registry.preload()
        assert registry.health().model_status == "READY"
        # Idempotent: second preload returns the same instances.
        en_before = registry.get_model("en")
        registry.preload()
        assert registry.get_model("en") is en_before

    def test_sessions_are_isolated_per_connection(self):
        """Two sessions must not share recognizer state (no cross-user leaks)."""
        import wave

        registry = VoskModelRegistry()
        registry.preload()
        session_a = registry.new_session("en")
        session_b = registry.new_session("en")
        assert session_a is not session_b

        fixture = REPO_ROOT / "backend" / "tests" / "fixtures" / "voice" / "en_next_step.wav"
        with wave.open(str(fixture), "rb") as wf:
            pcm = wf.readframes(wf.getnframes())

        finals_a = []
        # Feed utterance + trailing silence to session A only.
        data = pcm + b"\x00\x00" * 16000 * 2
        for i in range(0, len(data), 3200):
            event = session_a.feed(data[i : i + 3200])
            if event and event["type"] == "final":
                finals_a.append(event)
        assert len(finals_a) == 1
        assert finals_a[0]["transcript"] == "next step"

        # Session B never received audio: no finals, no shared state.
        assert session_b.final_count == 0
        event_b = session_b.feed(b"\x00\x00" * 160)
        assert event_b is None or event_b["type"] != "final"
