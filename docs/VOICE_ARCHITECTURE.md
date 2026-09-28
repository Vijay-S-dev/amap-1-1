# AMAP Voice Architecture — Vosk Streaming (single engine)

AMAP has exactly **one** speech-recognition engine: **Vosk** (offline,
streaming, free-form). The previous faster-whisper batch pipeline was removed
completely (see `VOSK_VOICE_FEASIBILITY_REPORT.md` for the investigation that
led to this decision).

## User experience

```
Idle → activate microphone → LISTENING → worker speaks (live partial captions)
→ worker stops speaking → automatic end-of-speech (Kaldi endpointer)
→ FINAL transcript → existing AMAP VoiceService parser + safety validation
→ command executes immediately → microphone returns to LISTENING
```

There is no stop-recording button, no audio upload, no recording cap, and no
execution from partial recognition.

## Pipeline

```
Browser microphone (getUserMedia)
  ↓ AudioWorklet: mono downmix, resample to 16 kHz, 16-bit PCM, 40 ms frames
WebSocket /api/v1/voice/stream?token=<JWT>&language=en|hi   (binary PCM ↑, JSON events ↓)
  ↓
VoskModelRegistry (both models loaded once per process at startup)
  ↓ new_session() — isolated KaldiRecognizer PER CONNECTION (no cross-user state)
Vosk streaming recognizer — FREE-FORM decoding (grammar constraints forbidden)
  ↓ partial events (display-only; NEVER carry a command payload)
Kaldi end-of-speech endpointer (in-model silence rules) — the ONLY finalizer
  ↓ final event
existing VoiceService.process_command (in-process, same code as /voice/process-command)
  ↓ matched command + requires_confirmation + validation_status
existing command execution / multimodal fusion (unchanged)
```

## Protocol (WS /api/v1/voice/stream)

Client → server:
- binary frames: 16-bit LE mono PCM at 16 kHz (browser worklet sends ~40 ms
  frames). Odd-length frames are rejected with `unsupported_audio_format`.
- text frames: JSON control messages (`{"type":"ping"}` → `{"type":"pong"}`).

Server → client:
- `{"type":"ready","language":...,"engine":"vosk","sample_rate":16000}`
- `{"type":"partial","text":...}` — display-only feedback
- `{"type":"final","transcript":...,"detected_language":...,"confidence":...,
  "command":{...VoiceServiceResult...},"utterance":N,"speech_end_s":...}`
  (an endpointer final on non-speech sends `"command": null`)
- `{"type":"error","code":...,"message":...}`

Close codes: `4401` unauthenticated, `4403` inactive user, `4400` bad
message/unsupported language, `4503` model unavailable.

Authentication uses the same JWT as the REST API (`AuthService.verify_token`),
passed as a `token` query parameter because browsers cannot set headers on
WebSocket connections. No unauthenticated voice execution path exists.

## Safety invariants

1. **Free-form decoding only.** Grammar-constrained Vosk decoding is
   forbidden: the feasibility investigation measured that grammar mode
   force-maps out-of-vocabulary speech onto valid command phrases
   ("Open production quality" → "up approve action call okay" → matched
   `confirm_action`). Out-of-vocabulary speech must stay unmatched.
2. **Partials never execute.** Only endpointer-finalized transcripts reach
   `VoiceService`. One final produces at most one command execution.
3. **No fallback engine.** If the Vosk models are unavailable, `/voice/stream`
   closes with `4503` and reports the error; no other engine is consulted.
4. **Isolated state.** Every WebSocket connection owns its own recognizer.
5. **No raw audio storage.** Frames are processed in memory and discarded.

## Models (deterministic provisioning)

Provisioned by `scripts/prefetch_vosk_models.py` into `backend/.vosk_cache/`
(gitignored; `AMAP_VOSK_MODELS_DIR` overrides):

| Language | Model | Version | Zip SHA-256 | Unpacked |
|---|---|---|---|---|
| English | `vosk-model-small-en-us-0.15` | 0.15 | `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498` | ~68 MB |
| Hindi | `vosk-model-small-hi-0.22` | 0.22 | `7c50a10866889f0ac21d912c20537a055a597ed09fc1d3e5bcd798f9f0017e48` | ~79 MB |

Source: `https://alphacephei.com/vosk/models/` (Apache-2.0). Every byte is
checksum-verified before installation; restricted networks fall back to
checksum-pinned GitHub mirrors. Installation is idempotent.

**Startup behavior:** `app/main.py` preloads both models once per process in a
background thread at startup (~1.3 s total on 2 vCPU). `GET /voice/stt-health`
reports `READY` / `ERROR` / `NOT_INITIALIZED`. Containers never download models
at runtime — the Docker backend image bakes the models in at **build** time
(`Dockerfile.backend` stage `vosk-models`), so startup is fully offline.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `WS /voice/stream` | streaming recognition (the worker pipeline) |
| `GET /voice/stt-health` | Vosk model status |
| `POST /voice/process-command` | transcript → command match (unchanged semantics; used by fusion/tooling) |

The old `POST /voice/transcribe` batch-upload endpoint was removed with
faster-whisper.

## Measured performance (2 vCPU sandbox, real HTTP)

| Metric | Value |
|---|---|
| Stream start → first partial | ~0.72 s (during speech — live caption) |
| Speech end → final transcript | 0.81–1.42 s (mean 1.07 s) |
| Final → command parse (in-process) | 0.1–9 ms |
| Command parse → execution (`/actions/execute`) | 37–49 ms |
| **Total speech end → command execution** | **1.02–1.46 s (mean 1.24 s)** |
| CPU during speech | ~21 % of one core |
| CPU continuous listening (open mic) | ~8 % of one core |
| Backend RSS (both models resident) | ~366 MB |
| Cold model load (both, one process) | ~1.3 s |

(Previous batch pipeline baseline for the same clips: 1.16–3.67 s speech end →
execution, with no live feedback and mic gaps — see the feasibility report.)

## Frontend integration

`frontend/shared/hooks/useVoiceStream.ts` — `getUserMedia` →
`AudioContext(16 kHz)` → inline AudioWorklet (`amap-pcm-sender`) → WebSocket,
with automatic reconnect (backoff), live partial state, and the state machine
`IDLE → REQUESTING_MIC → CONNECTING → LISTENING → SPEAKING → FINALIZING →
EXECUTING → READY` (+ `ERROR`). Consumed by the worker MultimodalHUD, onboarding
voice setup, and training. The old `useVoiceRecorder` (MediaRecorder batch
upload) was removed.

Tests: `backend/tests/test_vosk_stt_service.py` (registry),
`backend/tests/test_vosk_streaming.py` (A–R matrix: recognition EN/HI,
partials, end-of-speech, pauses, silence, noise, partial-safety,
exactly-once, consecutive commands, reconnect, auth, invalid audio, model
unavailable, out-of-vocabulary, multimodal fusion),
`backend/tests/test_phase11_voice_e2e.py` (real streaming → execution →
PostgreSQL audit), `frontend/tests/voice-worklet.test.ts` (browser PCM DSP),
`scripts/test_voice_endpoint.py` (live smoke),
`scripts/measure_vosk_performance.py` (latency/CPU/RAM measurement).
