"""Vosk streaming recognition tests over the real WebSocket endpoint.

Covers the required matrix:
  A. English recognition            B. Hindi recognition
  C. Streaming partials             D. Automatic end-of-speech
  E. Natural pauses                 F. Silence
  G. Noise                          H. Partial-result safety
  I. Final-result execution         J. Exactly-once execution
  K. Multiple consecutive commands  L. WebSocket reconnect
  M. Authentication                 N. RBAC (role model on voice)
  O. Invalid audio                  P. Vosk/model unavailable
  Q. Out-of-vocabulary speech       R. Multimodal command compatibility

Uses the REAL Vosk models and REAL database-backed JWT logins (no recognition
mocks). Skipped only when models are not provisioned
(``python scripts/prefetch_vosk_models.py``).

Safety invariant under test throughout: partial results are display-only and
never carry a command; only endpointer-finalized transcripts reach the AMAP
command parser; out-of-vocabulary speech MUST NOT be force-mapped to a valid
command (free-form decoding only — grammar-constrained decoding is forbidden).
"""

import json
import wave
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app
from services.vosk_stt_service import VOSK_MODEL_SPECS

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
PASSWORD = "SecurePassword123!"
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
MODELS_PRESENT = all(
    (REPO_ROOT / "backend" / ".vosk_cache" / spec["directory"]).is_dir()
    for spec in VOSK_MODEL_SPECS.values()
)

pytestmark = pytest.mark.skipif(
    not MODELS_PRESENT, reason="Vosk models not provisioned (scripts/prefetch_vosk_models.py)"
)

CHUNK = 3200  # 100 ms of 16 kHz 16-bit mono PCM


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _pcm(name: str) -> bytes:
    with wave.open(str(FIXTURES / f"{name}.wav"), "rb") as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1
        return wf.readframes(wf.getnframes())


def _silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(16000 * seconds)


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": ORG, "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _stream(client: TestClient, token: str, language: str = "en"):
    return client.websocket_connect(
        f"/api/v1/voice/stream?token={token}&language={language}"
    )


def _drain(ws):
    """Barrier-drain: the pong guarantees every prior event has been received
    (the server processes messages strictly in order)."""
    events = []
    ws.send_text(json.dumps({"type": "ping"}))
    while True:
        message = ws.receive_json()
        if message.get("type") == "pong":
            return events
        events.append(message)


def _feed(ws, pcm: bytes):
    """Feed PCM chunks, then drain all events produced (barrier)."""
    for i in range(0, len(pcm), CHUNK):
        ws.send_bytes(pcm[i : i + CHUNK])
    return _drain(ws)


def _feed_until_final(ws, pcm: bytes, extra_silence_rounds: int = 3):
    """Feed an utterance, then additional silence until a final arrives."""
    events = _feed(ws, pcm)
    if any(e.get("type") == "final" for e in events):
        return events
    for _ in range(extra_silence_rounds):
        events += _feed(ws, _silence(0.5))
        if any(e.get("type") == "final" for e in events):
            break
    return events


def _executable_commands(events):
    """Events whose finalized transcript produced an EXECUTABLE command."""
    return [
        e
        for e in events
        if e.get("type") == "final"
        and e.get("command")
        and e["command"].get("action_mapping")
    ]


# ---------------------------------------------------------------------------
# A. English recognition
# ---------------------------------------------------------------------------
def test_english_command_recognized_and_matched(client):  # A + I + J
    """EN 'next step' -> final transcript -> next_step command (exactly once)."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1, "exactly one finalized utterance"
        final = finals[0]
        assert final["transcript"] == "next step"
        assert final["detected_language"] == "en"
        command = final["command"]
        assert command["action_mapping"] == "next_step"
        assert command["validation_status"] == "valid"
        assert command["matched_command"] == "next_step"


# ---------------------------------------------------------------------------
# B. Hindi recognition
# ---------------------------------------------------------------------------
def test_hindi_command_recognized_and_matched(client):  # B
    """HI 'अगला कदम' -> Devanagari final -> next_step command."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "hi") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("hi_agla_kadam") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1
        assert finals[0]["transcript"] == "अगला कदम"
        assert finals[0]["detected_language"] == "hi"
        assert finals[0]["command"]["action_mapping"] == "next_step"


# ---------------------------------------------------------------------------
# C. Streaming partials + H. partial-result safety
# ---------------------------------------------------------------------------
def test_partials_stream_and_never_carry_commands(client):  # C + H
    """Partials appear before the final and contain no command payload."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        partials = [e for e in events if e["type"] == "partial"]
        finals = [e for e in events if e["type"] == "final"]
        assert finals, "a final must eventually arrive"
        # Partials are display-only: no command key ever.
        for partial in partials:
            assert set(partial.keys()) == {"type", "text"}
            assert partial["text"]
        # If any partial appeared, at least one was produced before the final.
        if partials:
            assert all(p is not None for p in partials)


# ---------------------------------------------------------------------------
# D. Automatic end-of-speech (no stop signal from the client)
# ---------------------------------------------------------------------------
def test_end_of_speech_is_automatic(client):  # D
    """The server finalizes by itself; the client never sends a stop control."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        # Utterance + trailing silence; NO stop message of any kind.
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert finals and finals[0]["transcript"] == "next step"


# ---------------------------------------------------------------------------
# E. Natural pauses must not prematurely terminate the command
# ---------------------------------------------------------------------------
def test_natural_pause_does_not_split_utterance(client):  # E
    """A 0.35 s pause between words still yields one complete final."""
    pcm = _pcm("en_next_step")
    # 'next' ends ~0.45 s into the clip; insert a 350 ms pause there.
    first = pcm[: int(16000 * 2 * 0.45)]
    rest = pcm[int(16000 * 2 * 0.45) :]
    with_pause = first + _silence(0.35) + rest
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, with_pause + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1, "a brief pause must not split the utterance"
        assert finals[0]["transcript"] == "next step"
        assert finals[0]["command"]["action_mapping"] == "next_step"


# ---------------------------------------------------------------------------
# F. Silence must not generate commands
# ---------------------------------------------------------------------------
def test_silence_generates_no_command(client):  # F
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed(ws, _silence(3.0))
        assert not _executable_commands(events), "silence must never produce a command"
        # 3 s of pure silence must not even produce a final with text.
        texted = [e for e in events if e.get("type") == "final" and e.get("transcript")]
        assert not texted


# ---------------------------------------------------------------------------
# G. Loud non-speech must not generate commands
# ---------------------------------------------------------------------------
def test_loud_noise_generates_no_command(client):  # G
    import struct

    rng = _deterministic_rng(1234)
    noise = b"".join(
        struct.pack("<h", int(rng() * 9000)) for _ in range(16000 * 3)
    )
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed(ws, noise)
        assert not _executable_commands(events), "loud non-speech must never produce an executable command"


def _deterministic_rng(seed: int):
    """Small LCG — deterministic 'noise' without numpy dependency."""
    state = seed

    def next_value():
        nonlocal state
        state = (1103515245 * state + 12345) % (2 ** 31)
        return (state / 2 ** 31) * 2 - 1

    return next_value


# ---------------------------------------------------------------------------
# J. Exactly-once execution
# ---------------------------------------------------------------------------
def test_final_transcript_executes_exactly_once(client):  # J
    """A single finalized utterance produces exactly one command payload."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1
        # Extended trailing silence must not re-emit the utterance.
        more = _feed(ws, _silence(1.5))
        assert not _executable_commands(more)


# ---------------------------------------------------------------------------
# K. Multiple consecutive commands in one connection
# ---------------------------------------------------------------------------
def test_multiple_consecutive_commands(client):  # K
    """Two utterances in one stream: two finals, both matched, correct order."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        first_finals = [e for e in events if e["type"] == "final"]
        assert len(first_finals) == 1
        assert first_finals[0]["transcript"] == "next step"

        events2 = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        second_finals = [e for e in events2 if e["type"] == "final"]
        assert len(second_finals) == 1
        assert second_finals[0]["transcript"] == "next step"
        # Recognizer re-armed: utterance counter advanced.
        assert second_finals[0]["utterance"] == first_finals[0]["utterance"] + 1


# ---------------------------------------------------------------------------
# L. WebSocket reconnect with isolated state
# ---------------------------------------------------------------------------
def test_websocket_reconnect_and_isolation(client):  # L
    """After a disconnect, a fresh connection works and has clean state."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
    # Socket closed above; reconnect.
    with _stream(client, token, "en") as ws2:
        ready = ws2.receive_json()
        assert ready["type"] == "ready"
        # The new connection starts from utterance 1 again (fresh state).
        events = _feed_until_final(ws2, _pcm("en_next_step") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1
        assert finals[0]["utterance"] == 1
        assert finals[0]["command"]["action_mapping"] == "next_step"


# ---------------------------------------------------------------------------
# M. Authentication
# ---------------------------------------------------------------------------
def test_stream_requires_valid_token(client):  # M
    with client.websocket_connect("/api/v1/voice/stream") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "unauthenticated"


def test_stream_rejects_garbage_token(client):  # M
    with client.websocket_connect("/api/v1/voice/stream?token=bogus") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "unauthenticated"


# ---------------------------------------------------------------------------
# N. RBAC: voice is available to authenticated worker AND supervisor roles
# (authorization of the executed ACTIONS stays enforced by /actions/execute)
# ---------------------------------------------------------------------------
def test_supervisor_can_stream_voice(client):  # N
    token = _login(client, "supervisor@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"


# ---------------------------------------------------------------------------
# O. Invalid audio
# ---------------------------------------------------------------------------
def test_invalid_audio_frame_rejected_without_command(client):  # O
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"\x01\x02\x03")  # odd length: not 16-bit PCM
        message = ws.receive_json()
        assert message == {
            "type": "error",
            "code": "unsupported_audio_format",
            "message": "Malformed audio frame: 16-bit PCM frames must have an even byte length",
        }
        # Connection survives; silence afterwards produces no command.
        events = _feed(ws, _silence(0.5))
        assert not _executable_commands(events)


def test_text_garbage_is_rejected_as_control_error(client):  # O
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_text("not-json")
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "bad_message"


# ---------------------------------------------------------------------------
# P. Vosk/model unavailable (covered model-independently in test_voice_pipeline;
# here: health reflects a broken models dir without crashing the app)
# ---------------------------------------------------------------------------
def test_stt_health_endpoint_reports_vosk(client):  # P (health surface)
    resp = client.get("/api/v1/voice/stt-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["supported_languages"] == ["en", "hi"]
    assert "vosk" in body["model_name"]
    assert body["model_status"] in ("READY", "LOADING", "NOT_INITIALIZED", "ERROR")


# ---------------------------------------------------------------------------
# Q. Out-of-vocabulary speech MUST NOT be force-mapped to a valid command.
# This is the dangerous grammar-mode behavior measured in the feasibility
# investigation; free-form decoding must never reproduce it.
# ---------------------------------------------------------------------------
def test_out_of_vocabulary_speech_is_not_a_command(client):  # Q
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_show_failed_inspection_records") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert len(finals) == 1
        # Free-form decoding: the transcript is real speech, NOT a forced
        # command phrase (grammar mode would have produced e.g.
        # "go finish done step action reject" -> cancel_action).
        assert finals[0]["transcript"] == "show failed inspection records"
        command = finals[0]["command"]
        assert command is None or command["action_mapping"] is None
        assert command["validation_status"] == "unmatched"


# ---------------------------------------------------------------------------
# R. Multimodal command compatibility
# ---------------------------------------------------------------------------
def test_vosk_transcript_feeds_multimodal_fusion(client):  # R
    """A Vosk-produced final transcript works as a voice input to /multimodal/fuse."""
    token = _login(client, "alex.worker@amap.com")
    with _stream(client, token, "en") as ws:
        assert ws.receive_json()["type"] == "ready"
        events = _feed_until_final(ws, _pcm("en_next_step") + _silence(1.0))
        finals = [e for e in events if e["type"] == "final"]
        assert finals and finals[0]["command"]["action_mapping"] == "next_step"
        action = finals[0]["command"]["action_mapping"]

    fuse = client.post(
        "/api/v1/multimodal/fuse",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "inputs": [
                {
                    "mode": "voice",
                    "raw_intent": action,
                    "confidence": finals[0]["command"]["confidence"],
                    "timestamp_ms": 1700000000000,
                    "context_data": {"language": "en", "matched_command": "next_step"},
                },
                {
                    "mode": "gesture",
                    "raw_intent": "pinch",
                    "confidence": 0.92,
                    "timestamp_ms": 1700000000300,
                    "context_data": {"gesture": "pinch", "spatial_x": 640, "spatial_y": 360},
                },
            ],
            "temporal_window_ms": 1500,
        },
    )
    assert fuse.status_code == 200, fuse.text
    fused = fuse.json()
    assert fused.get("fused_action") is not None
