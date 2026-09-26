"""Phase 11: genuine voice end-to-end test with real Whisper inference.

Chain under test (no mocked transcription when the local model exists):
  audio fixture -> POST /voice/transcribe (faster-whisper) ->
  POST /voice/process-command (matched intent) ->
  POST /actions/execute (authorization + safety) ->
  execution_events row in PostgreSQL.

Skipped only when the prefetched model is absent (run
``python scripts/prefetch_whisper_model.py`` on a fresh environment).
"""

from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"
DEFAULT_PASSWORD = "SecurePassword123!"
REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PRESENT = (REPO_ROOT / "backend" / ".whisper_cache" / "tiny" / "model.bin").is_file()

pytestmark = pytest.mark.skipif(
    not MODEL_PRESENT,
    reason="local whisper model not prefetched (scripts/prefetch_whisper_model.py)",
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


def _pg(sql: str, params=None):
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


def test_real_stt_english_transcription_and_execution(client):
    """Real model transcription -> matched command -> executed action -> PG."""
    token = _login(client, "alex.worker@amap.com")
    wav = (REPO_ROOT / "scripts" / "next_step.wav").read_bytes()

    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("next_step.wav", wav, "audio/wav")},
        data={"language": "en"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    transcript = resp.json()["transcript"].strip()
    assert transcript, "real STT must return a non-empty transcript"
    assert resp.json()["detected_language"] == "en"

    # intent recognition on the REAL transcript
    cmd = client.post(
        "/api/v1/voice/process-command",
        json={"raw_transcript": transcript, "confidence": 0.9, "language": "en"},
        headers=_auth(token),
    )
    assert cmd.status_code == 200, cmd.text
    action = cmd.json()["action_mapping"]
    assert action == "next_step", cmd.json()

    # execution with authorization + PG audit evidence
    before = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    marker = str(uuid4())
    ex = client.post(
        "/api/v1/actions/execute",
        json={"action_name": action, "parameters": {"source": "voice-e2e", "marker": marker}},
        headers=_auth(token),
    )
    assert ex.status_code == 200, ex.text
    assert ex.json()["success"] is True

    rows = _pg(
        "SELECT event_data, worker_profile_id FROM execution_events "
        "WHERE event_type = %s ORDER BY created_at DESC LIMIT 1",
        (f"action.{action}.executed",),
    )
    assert rows, "execution event must be persisted in PostgreSQL"
    data = rows[0][0]
    if isinstance(data, str):
        import json as _json
        data = _json.loads(data)
    assert data["parameters"]["marker"] == marker
    assert str(rows[0][1]) == ALEX

    after = _pg("SELECT COUNT(*) FROM execution_events")[0][0]
    assert after == before + 1

    # cleanup the evidence row created by this test
    _pg(
        "DELETE FROM execution_events WHERE event_data->'parameters'->>'marker' = %s",
        (marker,),
    )


def test_real_stt_hindi_transcription_and_matching(client):
    """Hindi fixture transcribed by the real model and recognized as a command."""
    token = _login(client, "alex.worker@amap.com")
    wav = (REPO_ROOT / "scripts" / "agla.wav").read_bytes()

    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("agla.wav", wav, "audio/wav")},
        data={"language": "hi"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    transcript = resp.json()["transcript"].strip()
    assert transcript, "Hindi STT must return a non-empty transcript"
    assert resp.json()["detected_language"] == "hi"

    cmd = client.post(
        "/api/v1/voice/process-command",
        json={"raw_transcript": transcript, "confidence": 0.9, "language": "hi"},
        headers=_auth(token),
    )
    assert cmd.status_code == 200, cmd.text
    assert cmd.json()["action_mapping"] == "next_step", cmd.json()


def test_voice_unauthorized_and_unsupported_paths(client):
    """Auth and language guards on the voice pipeline."""
    wav = (REPO_ROOT / "scripts" / "next_step.wav").read_bytes()

    # unauthenticated transcription rejected
    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("next_step.wav", wav, "audio/wav")},
        data={"language": "en"},
    )
    assert resp.status_code in (401, 403), resp.text

    token = _login(client, "alex.worker@amap.com")
    # unsupported language rejected with a clear 422
    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("next_step.wav", wav, "audio/wav")},
        data={"language": "fr"},
        headers=_auth(token),
    )
    assert resp.status_code == 422, resp.text

    # unauthenticated execution rejected
    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step", "parameters": {}},
    )
    assert resp.status_code in (401, 403), resp.text
