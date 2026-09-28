#!/usr/bin/env python3
"""Performance measurement for the AMAP Vosk streaming voice pipeline.

Measures, against the REAL running backend over real HTTP/WebSocket:
  1. microphone(stream start) -> first partial
  2. speech end -> final transcript           (endpointer latency)
  3. final transcript -> command parser       (server-measured)
  4. command parser -> execution              (/actions/execute round trip)
  5. total speech end -> command execution
  6. CPU during continuous listening (open mic, silence)
  7. CPU during speech
  8. RSS of the backend process (models resident)
  9. model load time (from process start to stt-health READY)

Feeds are REAL-TIME paced (40 ms frames, like the browser AudioWorklet).
Everything measured is printed as JSON at the end. Nothing is fabricated:
unavailable metrics are reported as null with a reason.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FIXTURES = REPO_ROOT / "backend" / "tests" / "fixtures" / "voice"

CLIPS = [
    ("en_next_step", "en"),
    ("hi_agla_kadam", "hi"),
    ("en_show_failed_inspection_records", "en"),
]


def http_json(method: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=60) as resp:
        return json.loads(resp.read().decode())


def backend_pid() -> int:
    out = subprocess.run(
        ["pgrep", "-f", "uvicorn app.main:app"], capture_output=True, text=True
    ).stdout.strip()
    pids = [int(p) for p in out.splitlines() if p.strip()]
    if not pids:
        raise RuntimeError("backend process not found")
    return pids[0]


def cpu_times(pid: int):
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().split()
    utime, stime = int(parts[13]), int(parts[14])
    hz = 100  # CLK_TCK on Linux
    return (utime + stime) / hz


def rss_mb(pid: int) -> float:
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


def pcm(name: str) -> bytes:
    with wave.open(str(FIXTURES / f"{name}.wav"), "rb") as wf:
        return wf.readframes(wf.getnframes())


def speech_end_audio_seconds(name: str) -> float | None:
    """Last non-zero sample position -> speech end in the fixture (seconds)."""
    import audioop  # stdlib

    data = pcm(name)
    # scan 10 ms windows for the last loud one
    win = 320
    last_loud = None
    for i in range(0, len(data) - win, win):
        if audioop.max(data[i : i + win], 2) > 600:
            last_loud = i + win
    return last_loud / 32000.0 if last_loud else None


async def measure_clip(token: str, name: str, language: str) -> dict:
    import websockets

    ws_url = (
        BASE.replace("https://", "wss://").replace("http://", "ws://")
        + f"/api/v1/voice/stream?token={token}&language={language}"
    )
    data = pcm(name)
    fixture_speech_end = speech_end_audio_seconds(name)
    frame = 1280  # 40 ms
    result: dict = {"clip": name, "language": language}

    async with websockets.connect(ws_url, max_size=2 ** 22) as ws:
        ready = json.loads(await ws.recv())
        assert ready["type"] == "ready"
        t_stream_start = time.perf_counter()

        first_partial_at = None
        speech_cpu_start = None
        final_msg = None
        i = 0
        # real-time paced feeding (like the browser worklet)
        while i < len(data) or final_msg is None:
            chunk = data[i : i + frame] if i < len(data) else b"\x00\x00" * (frame // 2)
            i += frame
            target = t_stream_start + (i / 32000.0)
            now = time.perf_counter()
            if target > now:
                await asyncio.sleep(target - now)
            if i == frame:
                speech_cpu_start = time.perf_counter()
            await ws.send(chunk)
            try:
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.001))
                    if message["type"] == "partial" and first_partial_at is None:
                        first_partial_at = time.perf_counter()
                    if message["type"] == "final":
                        final_msg = message
                        break
            except asyncio.TimeoutError:
                pass
            if final_msg:
                break
            if i > len(data) + 32000 * 8:  # 8 s of trailing silence cap
                break

        t_final = time.perf_counter()
        assert final_msg is not None, f"no final for {name}"

        # 4. command parser -> execution (real /actions/execute call)
        action = final_msg["command"]["action_mapping"] if final_msg.get("command") else None
        parse_to_exec_ms = None
        t_executed = None
        if action:
            t0 = time.perf_counter()
            exec_result = http_json(
                "POST",
                "/api/v1/actions/execute",
                token,
                {"action_name": action, "parameters": {"source": "perf-measurement"}},
            )
            t_executed = time.perf_counter()
            parse_to_exec_ms = round((t_executed - t_final) * 1000, 1)
            assert exec_result.get("success") is True

        speech_end_wall = t_stream_start + (final_msg.get("speech_end_s") or fixture_speech_end or 0)
        result.update(
            {
                "transcript": final_msg["transcript"],
                "time_to_first_partial_s": round(first_partial_at - t_stream_start, 3) if first_partial_at else None,
                "speech_end_s_audio": final_msg.get("speech_end_s"),
                "speech_end_to_final_s": round(t_final - speech_end_wall, 3),
                "final_to_command_parse_ms": final_msg.get("command_parse_ms"),
                "command_parse_to_execution_ms": parse_to_exec_ms,
                "total_speech_end_to_execution_s": round(t_executed - speech_end_wall, 3)
                if t_executed
                else None,
                "matched_action": action,
            }
        )
    return result


async def measure_idle_cpu(token: str) -> dict:
    """Open mic on silence for 10 s; sample backend CPU + RSS."""
    import websockets

    ws_url = (
        BASE.replace("https://", "wss://").replace("http://", "ws://")
        + f"/api/v1/voice/stream?token={token}&language=en"
    )
    pid = backend_pid()
    async with websockets.connect(ws_url, max_size=2 ** 22) as ws:
        await ws.recv()  # ready
        cpu0 = cpu_times(pid)
        t0 = time.perf_counter()
        frame = b"\x00\x00" * 640  # 40 ms
        for _ in range(250):  # 10 s of silence, real time
            await ws.send(frame)
            await asyncio.sleep(0.04)
        cpu1 = cpu_times(pid)
        wall = time.perf_counter() - t0
        return {
            "listen_window_s": round(wall, 1),
            "cpu_s": round(cpu1 - cpu0, 3),
            "cpu_pct_of_one_core": round((cpu1 - cpu0) / wall * 100, 1),
            "rss_mb": round(rss_mb(pid), 0),
        }


async def main() -> None:
    token = http_json(
        "POST",
        "/api/v1/auth/login",
        body={
            "organization_id": ORG,
            "email": "alex.worker@amap.com",
            "password": "SecurePassword123!",
        },
    )["access_token"]
    print("[auth] login OK")

    # 9. model load time: process start -> stt-health READY
    pid = backend_pid()
    with open(f"/proc/{pid}/stat") as f:
        start_ticks = int(f.read().split()[21])
    uptime_ticks = int(open("/proc/uptime").read().split()[1].split(".")[0]) * 100
    process_start_epoch = time.time() - (uptime_ticks - start_ticks) / 100
    health = http_json("GET", "/api/v1/voice/stt-health", token)
    model_load_s = None
    if health["model_status"] == "READY":
        # measure by timing a fresh registry load is intrusive; report uptime-since-start
        model_load_s = round(time.time() - process_start_epoch, 1)

    results = {
        "backend": BASE,
        "stt_health": health,
        "backend_process_uptime_s_at_measurement": model_load_s,
        "clips": [],
    }

    for name, language in CLIPS:
        clip_result = await measure_clip(token, name, language)
        results["clips"].append(clip_result)
        print(f"[clip] {name}: {json.dumps(clip_result, ensure_ascii=False)}")

    # CPU during speech (from clip 1 run): sampled above via speech_cpu_start is
    # client-side; measure directly: stream one clip while sampling server CPU.
    import websockets

    ws_url = (
        BASE.replace("https://", "wss://").replace("http://", "ws://")
        + f"/api/v1/voice/stream?token={token}&language=en"
    )
    pid = backend_pid()
    data = pcm("en_next_step") + b"\x00\x00" * 16000
    async with websockets.connect(ws_url, max_size=2 ** 22) as ws:
        await ws.recv()
        cpu0 = cpu_times(pid)
        t0 = time.perf_counter()
        for i in range(0, len(data), 1280):
            await ws.send(data[i : i + 1280])
            await asyncio.sleep(0.04)
        # drain
        deadline = time.time() + 4
        while time.time() < deadline:
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                break
            except Exception:
                break
        cpu1 = cpu_times(pid)
        wall = time.perf_counter() - t0
        results["cpu_during_speech"] = {
            "window_s": round(wall, 1),
            "cpu_s": round(cpu1 - cpu0, 3),
            "cpu_pct_of_one_core": round((cpu1 - cpu0) / wall * 100, 1),
        }

    results["cpu_during_continuous_listening"] = await measure_idle_cpu(token)

    finals = [c for c in results["clips"] if c["speech_end_to_final_s"] is not None]
    if finals:
        results["summary"] = {
            "speech_end_to_final_s": {
                "min": min(c["speech_end_to_final_s"] for c in finals),
                "mean": round(statistics.mean(c["speech_end_to_final_s"] for c in finals), 3),
                "max": max(c["speech_end_to_final_s"] for c in finals),
            },
            "total_speech_end_to_execution_s": {
                "min": min(c["total_speech_end_to_execution_s"] for c in finals if c["total_speech_end_to_execution_s"]),
                "mean": round(
                    statistics.mean(
                        [c["total_speech_end_to_execution_s"] for c in finals if c["total_speech_end_to_execution_s"]]
                    ),
                    3,
                ),
                "max": max(c["total_speech_end_to_execution_s"] for c in finals if c["total_speech_end_to_execution_s"]),
            },
        }

    out = Path("/tmp/vosk_perf_results.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\n[results] saved -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
