#!/usr/bin/env python3
"""Live smoke test for the AMAP streaming voice pipeline (Vosk).

Runs against a real backend (default http://127.0.0.1:8000):
  1. login (real PostgreSQL user)
  2. open WS /api/v1/voice/stream
  3. stream a 16 kHz PCM fixture in 40 ms frames (real-time paced)
  4. print partial events as they arrive (display-only)
  5. print the endpointer-finalized transcript + matched AMAP command
  6. verify the old batch endpoint is gone (404 on /voice/transcribe)

Usage:
  python scripts/test_voice_endpoint.py [fixture.wav] [language] [base_url]

Requires: pip install websockets  (uvicorn[standard] environments already have it)
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import urllib.request
import uuid
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"

DEFAULT_FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "voice" / "en_next_step.wav"
DEFAULT_LANGUAGE = "en"
DEFAULT_BASE = "http://127.0.0.1:8000"


def login(base_url: str) -> str:
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        data=json.dumps(
            {
                "organization_id": ORG,
                "email": "alex.worker@amap.com",
                "password": "SecurePassword123!",
            }
        ).encode(),
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


async def stream(base_url: str, token: str, fixture: Path, language: str) -> int:
    import websockets

    ws_url = (
        base_url.replace("https://", "wss://").replace("http://", "ws://")
        + f"/api/v1/voice/stream?token={token}&language={language}"
    )

    with wave.open(str(fixture), "rb") as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1 and wf.getsampwidth() == 2, (
            "fixture must be 16 kHz mono 16-bit PCM"
        )
        pcm = wf.readframes(wf.getnframes())

    frame_bytes = int(16000 * 2 * 0.04)  # 40 ms frames, like the browser worklet
    async with websockets.connect(ws_url, max_size=2 ** 22) as ws:
        ready = json.loads(await ws.recv())
        print(f"[ready] engine={ready.get('engine')} language={ready.get('language')} "
              f"sample_rate={ready.get('sample_rate')}")

        async def sender():
            for i in range(0, len(pcm), frame_bytes):
                await ws.send(pcm[i : i + frame_bytes])
                await asyncio.sleep(0.04)  # real-time pacing like a microphone
            # keep the mic open with silence; the endpointer finalizes on its own
            for _ in range(50):
                await ws.send(b"\x00\x00" * frame_bytes)
                await asyncio.sleep(0.04)

        send_task = asyncio.create_task(sender())
        final_seen = False
        try:
            while True:
                try:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                except asyncio.TimeoutError:
                    break
                if message["type"] == "partial":
                    print(f"[partial] {message['text']!r}   (display-only)")
                elif message["type"] == "final":
                    final_seen = True
                    print(f"[final]   transcript={message['transcript']!r} "
                          f"language={message['detected_language']} "
                          f"confidence={message.get('confidence')}")
                    command = message.get("command")
                    if command:
                        print(f"[command] matched={command.get('matched_command')} "
                              f"action={command.get('action_mapping')} "
                              f"status={command.get('validation_status')} "
                              f"requires_confirmation={command.get('requires_confirmation')}")
                        if not command.get("action_mapping"):
                            print("[command] unmatched — no command executes (correct for OOV speech)")
                    break
                elif message["type"] == "error":
                    print(f"[error]   {message.get('code')}: {message.get('message')}")
                    return 2
        finally:
            send_task.cancel()
        return 0 if final_seen else 1


def check_batch_endpoint_removed(base_url: str, token: str) -> None:
    """The old whisper batch upload endpoint must be gone (404/405)."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="audio"; filename="clip.webm"\r\n'
        "Content-Type: audio/webm\r\n\r\n"
    ).encode() + b"\x00\x00" * 1600 + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{base_url}/api/v1/voice/transcribe", method="POST", data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        urllib.request.urlopen(req, timeout=15)
        print("[regression] /voice/transcribe still exists — should be removed!")
    except urllib.error.HTTPError as exc:
        status = "removed" if exc.code in (404, 405) else f"HTTP {exc.code}"
        print(f"[regression] /voice/transcribe: {status}")


def main() -> int:
    fixture = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    language = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LANGUAGE
    base_url = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_BASE

    print(f"AMAP streaming voice smoke test -> {base_url} ({fixture.name}, lang={language})")
    token = login(base_url)
    print("[auth]    login OK")

    check_batch_endpoint_removed(base_url, token)

    result = asyncio.run(stream(base_url, token, fixture, language))
    if result == 0:
        print("[result]  PASS — endpointer finalized the utterance automatically")
    else:
        print("[result]  FAIL — no finalized utterance received")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
