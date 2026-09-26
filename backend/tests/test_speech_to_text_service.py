"""Unit coverage for the local STT service without downloading Whisper."""

import os
import subprocess

import pytest

from services.speech_to_text_service import STTModelState, SpeechToTextService


@pytest.fixture(autouse=True)
def reset_service():
    SpeechToTextService.reset_for_tests()
    yield
    SpeechToTextService.reset_for_tests()


def test_service_is_lazy_and_singleton():
    first = SpeechToTextService()
    second = SpeechToTextService()
    assert first is second
    assert first.state is STTModelState.NOT_INITIALIZED
    assert first.health().supported_languages == ["en", "hi"]


def test_language_validation_only_allows_english_and_hindi():
    service = SpeechToTextService()
    assert service.validate_language("en-US") == "en"
    assert service.validate_language("hi-IN") == "hi"
    assert service.validate_language(None) is None
    with pytest.raises(ValueError):
        service.validate_language("de")


def test_empty_audio_is_rejected_without_model_load():
    service = SpeechToTextService()
    with pytest.raises(ValueError, match="empty"):
        service._audio_to_wav(b"", "audio.webm")
    assert service.state is STTModelState.NOT_INITIALIZED


def test_ffmpeg_converts_audio_to_temporary_wav(monkeypatch):
    service = SpeechToTextService()
    calls = []

    monkeypatch.setattr(
        "services.speech_to_text_service.shutil.which",
        lambda executable: r"C:\ffmpeg\bin\ffmpeg.exe" if executable == "ffmpeg" else None,
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        output_path = command[-1]
        with open(output_path, "wb") as output:
            output.write(b"RIFF-test-wav")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("services.speech_to_text_service.subprocess.run", fake_run)

    converted = service._audio_to_wav(b"m4a-test", "Recording.m4a")
    try:
        assert os.path.exists(converted.path)
        command, kwargs = calls[0]
        assert command[0].endswith("ffmpeg.exe")
        assert command[command.index("-i") + 1].endswith(".m4a")
        assert command[-1].endswith(".wav")
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 30
    finally:
        os.unlink(converted.path)


def test_ffmpeg_unavailable_has_clear_error(monkeypatch):
    service = SpeechToTextService()
    monkeypatch.setattr("services.speech_to_text_service.shutil.which", lambda _: None)
    # also block the bundled imageio-ffmpeg fallback
    monkeypatch.setattr(
        "services.speech_to_text_service._resolve_ffmpeg", lambda: None
    )

    with pytest.raises(ValueError, match="FFmpeg executable was not found"):
        service._audio_to_wav(b"audio", "Recording.m4a")


def test_ffmpeg_falls_back_to_bundled_binary(monkeypatch):
    """PATH lookup failing must not break audio decode: the declared
    imageio-ffmpeg dependency provides a bundled executable instead."""
    service = SpeechToTextService()
    import imageio_ffmpeg

    bundled = imageio_ffmpeg.get_ffmpeg_exe()
    monkeypatch.setattr("services.speech_to_text_service.shutil.which", lambda _: None)

    assert (
        Path := __import__("pathlib").Path
    )  # noqa: F841
    from services.speech_to_text_service import _resolve_ffmpeg

    assert _resolve_ffmpeg() == bundled


def test_confidence_calculation_exponential_bounds():
    service = SpeechToTextService()

    class MockSegment:
        def __init__(self, avg_logprob):
            self.avg_logprob = avg_logprob

    # Realistic avg_logprob values
    c1 = service._confidence([MockSegment(-0.1)])
    c2 = service._confidence([MockSegment(-0.5)])
    c3 = service._confidence([MockSegment(-1.0)])
    c4 = service._confidence([MockSegment(-2.0)])

    # Output within [0, 1]
    assert 0.0 <= c4 <= c3 <= c2 <= c1 <= 1.0
    # Monotonic decrease as logprob becomes more negative
    assert c1 > c2 > c3 > c4
    # No false zero caused by linear mapping (previous linear formula produced 0.0 for -1.0)
    assert c3 > 0.35
    assert c4 > 0.10


def test_unsupported_auto_detected_language_fails_closed(monkeypatch):
    service = SpeechToTextService()

    # Mock audio conversion to avoid needing ffmpeg
    class DummyAudioFile:
        path = "dummy.wav"
        temporary = False

    monkeypatch.setattr(service, "_audio_to_wav", lambda *args, **kwargs: DummyAudioFile())

    class DummyInfo:
        language = "de"  # German auto-detected

    class DummySegment:
        text = "weiter"
        avg_logprob = -0.2

    class DummyModel:
        def transcribe(self, *args, **kwargs):
            return [DummySegment()], DummyInfo()

    monkeypatch.setattr(service, "_load_model", lambda: DummyModel())

    result = service.transcribe(b"dummy_audio_bytes", language=None)
    assert result.success is False
    assert result.transcript == ""
    assert result.detected_language == "de"
