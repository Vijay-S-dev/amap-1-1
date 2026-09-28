"""Phase 11: genuine voice end-to-end test with real Vosk streaming inference.

Chain under test (no mocked recognition when the local models exist):
  audio fixture -> WS /voice/stream (Vosk streaming + endpointer) ->
  finalized transcript -> existing VoiceService match (rides on the final
  event) -> POST /actions/execute (authorization + safety) ->
  execution_events row in PostgreSQL.

Skipped only when the Vosk models are absent (run
``python scripts/prefetch_vosk_models.py`` on a fresh environment).
"""

import json
import wave
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app
from services.vosk_stt_service import VOSK_MODEL_SPECS

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"
DEFAULT_PASSWORD = "SecurePassword123!"
REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_PRESENT = all(
    (REPO_ROOT / "backend" / ".vosk_cache" / spec["directory"]).is_dir()
    for spec in VOSK_MODEL_SPECS.values()
)
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"

pytestmark = pytest.mark.skipif(
    not MODELS_PRESENT,
    reason="local Vosk models not provisioned (scripts/prefetch_vosk_models.py)",
)


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": ORG, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _pcm(name: str) -> bytes:
    with wave.open(str(FIXTURES / f"{name}.wav"), "rb") as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1
        return wf.readframes(wf.getnframes())


def _silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(16000 * seconds)


def _stream_final(client: TestClient, token: str, language: str, clip: str) -> dict:
    """Stream one clip over the WebSocket and return the final event."""
    with client.websocket_connect(
        f"/api/v1/voice/stream?token={token}&language={language}"
    ) as ws:
        assert ws.receive_json()["type"] == "ready"
        pcm = _pcm(clip)
        # Feed the utterance, then additional trailing silence in rounds
        # until the endpointer fires (some clips need >1 s of silence).
        for i in range(0, len(pcm), 3200):
            ws.send_bytes(pcm[i : i + 3200])
        for _ in range(6):
            for i in range(0, len(_silence(0.5)), 3200):
                ws.send_bytes(_silence(0.5)[i : i + 3200])
            ws.send_text(json.dumps({"type": "ping"}))
            while True:
                message = ws.receive_json()
                if message.get("type") == "pong":
                    break
                if message.get("type") == "final":
                    return message
        raise AssertionError("endpoint never finalized the utterance")


def _pg(sql: str, params=None):
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


def test_real_stt_english_streaming_and_execution(client):
    """Real Vosk streaming -> matched command -> executed action -> PG audit."""
    token = _login(client, "alex.worker@amap.com")

    final = _stream_final(client, token, "en", "en_next_step")
    transcript = final["transcript"].strip()
    assert transcript, "real streaming STT must return a non-empty transcript"
    assert final["detected_language"] == "en"

    # intent recognition result rides on the final event (same VoiceService)
    command = final["command"]
    assert command["action_mapping"] == "next_step", command
    assert command["validation_status"] == "valid"

    # execution with authorization + PG audit evidence
    before = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    marker = str(uuid4())
    ex = client.post(
        "/api/v1/actions/execute",
        json={"action_name": command["action_mapping"], "parameters": {"source": "voice-e2e", "marker": marker}},
        headers=_auth(token),
    )
    assert ex.status_code == 200, ex.text
    assert ex.json()["success"] is True

    rows = _pg(
        "SELECT event_data, worker_profile_id FROM execution_events "
        "WHERE event_type = %s ORDER BY created_at DESC LIMIT 1",
        (f"action.{command['action_mapping']}.executed",),
    )
    assert rows, "execution event must be persisted in PostgreSQL"
    data = rows[0][0]
    if isinstance(data, str):
        data = json.loads(data)
    assert data["parameters"]["marker"] == marker
    assert str(rows[0][1]) == ALEX

    after = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    assert after == before + 1

    # cleanup the evidence row created by this test
    _pg(
        "DELETE FROM execution_events WHERE event_data->'parameters'->>'marker' = %s",
        (marker,),
    )


def test_real_stt_hindi_streaming_and_matching(client):
    """Hindi fixture streamed through Vosk and recognized as a command."""
    token = _login(client, "alex.worker@amap.com")

    final = _stream_final(client, token, "hi", "hi_agla_kadam")
    transcript = final["transcript"].strip()
    assert transcript, "Hindi streaming STT must return a non-empty transcript"
    assert transcript == "अगला कदम"
    assert final["detected_language"] == "hi"
    assert final["command"]["action_mapping"] == "next_step", final["command"]


def test_real_stt_out_of_vocabulary_is_not_executed(client):
    """Out-of-vocabulary English speech must stay unmatched (no false command)."""
    token = _login(client, "alex.worker@amap.com")
    final = _stream_final(client, token, "en", "en_show_failed_inspection_records")
    assert final["transcript"] == "show failed inspection records"
    command = final["command"]
    assert command is None or command["action_mapping"] is None
    assert command["validation_status"] == "unmatched"


def test_voice_unauthorized_paths(client):
    """Auth guards on the streaming voice pipeline."""
    # unauthenticated streaming rejected with a clear error + close
    with client.websocket_connect("/api/v1/voice/stream") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "unauthenticated"

    # unauthenticated execution rejected
    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step", "parameters": {}},
    )
    assert resp.status_code in (401, 403), resp.text

    # unauthenticated command parsing rejected
    resp = client.post(
        "/api/v1/voice/process-command",
        json={"raw_transcript": "next step", "confidence": 0.9, "language": "en"},
    )
    assert resp.status_code in (401, 403), resp.text
