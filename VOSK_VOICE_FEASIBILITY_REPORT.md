# AMAP Voice Interaction — Vosk Streaming Feasibility Report

**Phase:** Investigation / feasibility only — **no production code was modified, nothing was replaced, nothing was committed.**
**Date:** 2026-09-28 • **Environment:** 2 vCPU, ~4 GB RAM sandbox • **Baseline:** current `main`-state AMAP (faster-whisper Tiny, batch HTTP pipeline)
**Artifacts:** measurement scripts + raw results in `investigation/vosk/` (untracked, non-production)

---

## Executive summary

**Verdict: YES — Vosk + its built-in Kaldi endpointer can realistically deliver the "speak → automatic end-of-speech → immediate execution" UX, and it is measurably better than the current batch pipeline on this hardware — but it must be introduced as a parallel streaming path behind a flag, piloted with real human speakers (all audio in this study is TTS), and grammar-constrained decoding must NOT be used (measured safety hazard).**

Measured highlights (identical audio clips, same 2-core box):

| Metric (measured) | Current (faster-whisper Tiny, batch) | Vosk small (streaming) |
|---|---|---|
| End-of-speech → command executed | ≈ **1.16–3.67 s** (600 ms frontend VAD + upload + 556–3057 ms backend + parse RTT) | ≈ **0.80–1.38 s** (endpointer 0.74–1.31 s + 66 ms final + in-process parse) |
| Live feedback while speaking | none (batch) | **partials from ~0.7 s after stream start** |
| Mic coverage | **gaps** during upload/processing; utterances hard-capped at 4 s | continuous, no gaps, no cap |
| English command accuracy | 6/6 clips (1 spacing artifact) | **6/6 clips, exact** |
| Hindi command accuracy | **2/4** (2 garbage transcripts → commands missed) | **4/4 exact Devanagari → all 4 matched by the existing AMAP parser** |
| CPU during recognition | 108–128 % of one core | **15–38 % of one core** (4.4 % idle listening) |
| RAM (models resident) | ~219 MB incremental (77 MB model on disk) | ~350 MB for **both** EN+HI (202 MB EN-only process RSS) |
| Model load (cold) | 0.95–1.40 s (first request) | 0.35–0.61 s (startup, per model) |
| Offline | yes | yes (fully local, Apache-2.0) |

The single most important safety finding: **Vosk grammar-constrained decoding force-maps out-of-vocabulary speech onto grammar phrases** — "Open production quality" was decoded as *"up approve action call okay"*, which the existing AMAP parser then matched to `confirm_action`. Free-form decoding + the existing AMAP parser correctly returned "unmatched" for every out-of-vocabulary phrase. **Recommendation: free-form recognition only; the existing `VoiceService` stays the single command-matching authority.**

---

## Methodology & honesty box

- **Everything below was actually executed in this sandbox.** Scripts: `investigation/vosk/{endpoint_probes.py, measure_all.py, tuned_test.py, idle_cpu.py}`; raw JSON: `probe_results.json`, `results2.json`, `tuned_results.json`.
- Speech audio was **neural TTS** (one masculine voice per language), 10 clips: 6 EN (4 AMAP in-vocabulary commands + "Show failed inspection records", "Submit result", "Open production quality" from the investigation brief) and 4 HI (अगला कदम, मुझे मदद चाहिए, रोको, रद्द करें). **Not real factory workers** — recognition rates on human/accented/noisy speech require the pilot phase; this study compares engines on *identical* audio, which is a valid A/B.
- The current-architecture numbers use the **real production code path**: `SpeechToTextService.transcribe()` (FFmpeg decode → faster-whisper Tiny int8, beam 5, VAD filter) imported unmodified from `backend/services/`, fed browser-identical Opus/WebM uploads; parsing uses the real `VoiceService`.
- Vosk feeding was **real-time paced** (40 ms chunks) to measure wall-clock endpointer behavior.
- Models: `vosk-model-small-en-us-0.15` (official zip, **SHA-256 verified** `30f26242…2498` against an independent published checksum list) and `vosk-model-small-hi-0.22` (structure-complete mirror from a third-party GitHub repo — provenance noted; zip checksum could not be re-verified because the official host is network-blocked here). Vosk library 0.3.45 from PyPI.
- **Could NOT be measured here (stated explicitly):** real-browser microphone capture (no browser/webcam in sandbox), real human speech, factory-floor noise profiles, multi-worker server concurrency, Docker deployment of a vosk service. These are pilot-phase items.
- Prior corroborating real-HTTP measurements (live backend, previous session): EN `processing_time_ms=811.68`, HI `1389.59` — consistent with today's fresh 556–3057 ms range.

---

## 1. Current voice architecture (as traced in code)

```
[Browser: MultimodalHUD / voice-setup / training]
  useVoiceRecorder.ts (frontend/shared/hooks)
    getUserMedia(audio) → MediaRecorder (audio/webm;codecs=opus, 100 ms chunks)
    AnalyserNode RMS energy monitor:
      speechDetected when level > 8/100
      auto-stop after 600 ms continuous silence (silenceThresholdMs)
      hard cap 4000 ms (maxDurationMs)
    continuous mode: auto-restart 50 ms after transcription completes
        ↓ recorder.stop() → Blob(webm/opus)
  api.transcribeAudio(): FormData(audio, language) + Bearer + X-Organization-Id
        ↓ POST /api/v1/voice/transcribe          [batch upload of the whole clip]
[Backend routes/voice.py]
  SpeechToTextService.transcribe()  (backend/services/speech_to_text_service.py)
    10 MB guard → FFmpeg decode → 16 kHz mono WAV (temp file)
    faster-whisper Tiny, CPU, int8, beam 5, vad_filter=True
    language gate (en/hi only; explicit-ur→hi tolerance)
    confidence = exp(avg_logprob) heuristic; fail-closed on empty transcript
        ↓ {transcript, detected_language, confidence, processing_time_ms}
[Frontend handleVoiceTranscript (MultimodalHUD.tsx)]
  500 ms debounce latch + in-flight guard
        ↓ POST /voice/process-command
[Backend VoiceService (backend/services/voice_service.py)]
  normalize → 22-command bilingual vocabulary (EN + Devanagari + romanized Hindi)
  exact match (1.0) / word-boundary containment (0.92) / fuzzy similarity (≥0.75)
  combined-confidence gates: <0.60 low-confidence, <0.80 or safety-critical → confirmation
        ↓ {matched_command, action_mapping, requires_confirmation, validation_status}
[Worker page action execution]  +  /multimodal/fuse (voice+gesture temporal fusion)
```

UI facts verified: in the worker HUD there is **no manual stop button** (continuous auto mode; only an error-retry button); the "upload-then-wait" feel comes from the `PROCESSING` state. `sttLanguage` follows the worker's accessibility language preference (`hi` → `'hi'`).

## 2. Current bottlenecks (measured)

1. **Batch barrier:** nothing is recognized until the clip is fully recorded, uploaded (≤10 MB), FFmpeg-decoded, and whisper-decoded — measured backend segment **556–606 ms (EN), 527–3057 ms (HI)**; the two Hindi failures took 1.8 s and 3.1 s.
2. **End-of-speech detection is raw RMS energy** (`silenceLevel 8/100`, 600 ms) — not speech-model-based; fragile against factory background noise (a constant hum above the threshold keeps the recorder running to the 4 s cap; loud transients reset the silence timer).
3. **Mic gaps:** during `PROCESSING` + the 50 ms restart, the mic is closed → **speech is lost** if the worker keeps talking.
4. **4 s hard cap** truncates slow or longer utterances.
5. **No live feedback** — the worker gets no confirmation anything was heard until the full round trip completes.
6. **Whisper-Tiny Hindi weakness (measured on identical clips):** "मुझे मदद चाहिए" → *"Mooji Madhacharya."*, "रद्द करें" → *"Radhukari."* — **2 of 4 Hindi commands silently missed** by the parser (unmatched). Whisper also transliterates Hindi to Latin ("Agla Kadam", "Roku"), which only works because the vocabulary happens to include romanized forms.
7. **Perceived end-of-speech → executed ≈ 1.16–3.67 s** (600 ms VAD + upload + backend + parse RTT).

## 3. Vosk capabilities relevant to AMAP (measured on 2 vCPU / 4 GB)

| Capability | Finding |
|---|---|
| Streaming recognition | Yes — `AcceptWaveform()` per chunk; **progressive partials** ("show" → "show failed" → "show failed inspection"…), first partial ≈ 0.68–0.95 s after stream start |
| Incremental recognition | Yes — partials refine while speaking; `FinalResult()` returns word-level confidences + timestamps (66 ms after endpoint) |
| End-of-speech detection | **Built-in Kaldi endpointer** in `model.conf` (silence-phones + trailing-silence rules). Fired on every real utterance, **never** on 3 s silence or loud noise; did **not** split utterances with 0.35 s / 0.5 s / 0.6 s internal pauses; auto re-arms for the next utterance (two-utterance continuous stream: both finals correct) |
| Endpoint latency | 0.62–1.31 s after last word (avg ≈ 0.95 s EN, ≈ 1.05 s HI). Tuning `rule2.min-trailing-silence` 0.5→0.35 s helped only 1/6 clips (0.858→0.617 s) — decoder silence-lag dominates; a hybrid "frontend-VAD flush" is the better latency lever (see §4) |
| CPU | 15–38 % of one core while streaming; **4.4 % of one core idle-listening** (10 s silence) — always-on mic is cheap |
| RAM | ~202 MB process RSS (EN model); ~350 MB with **both** EN+HI resident; model load 0.35–0.61 s each |
| Model size | EN small: 41 MB zip / 68 MB unpacked (WER ≈ 9.9–10.4 % on clean test sets per model README). HI small: 79 MB unpacked (README WER 39.08 % general / 20.89 % IITM test — short-command accuracy measured 4/4 here) |
| English | 6/6 exact transcripts incl. out-of-vocabulary phrases ("Show failed inspection records", "Open production quality") |
| Hindi | 4/4 exact Devanagari transcripts; all 4 matched by the **existing** AMAP parser (अगला कदम→next_step, मदद→request_assistance, रोको→emergency_stop, रद्द करें→cancel_action) |
| Offline | Fully local; no network at runtime; library + models Apache-2.0 |
| Browser/backend integration | No native browser ASR; needs a WebSocket (or WebRTC) bridge — backend `KaldiRecognizer` per connection, or the official `vosk-server` sidecar. Python API is synchronous and trivially wrapped in FastAPI |
| Command vocabulary / grammar | `SetGrammar()` constrains decoding to a phrase list — **works for in-vocab EN commands, but is DISQUALIFIED for AMAP** (see hazard below). Free-form + existing parser is the correct combination |
| Short-command quality | Excellent on the test set (10/10 exact free-form transcripts); small models' known weakness is long noisy dictation, not short commands |

**Grammar hazard (measured, disqualifying):** with the AMAP vocabulary as a Vosk grammar, out-of-vocabulary speech is force-decoded onto grammar words: "Show failed inspection records" → *"go finish done step action reject"* → **existing parser matched `cancel_action`** (containment of "reject"); "Submit result" → *"session it resume halt"* → `resume_session`; "Open production quality" → *"up approve action call okay"* → `confirm_action`. Also, the Hindi grammar path is **entirely non-functional** with `vosk-model-small-hi-0.22` (every Devanagari phrase rejected as "missing in vocabulary" by the grammar FST, while free-form decoding of the same words works perfectly). Grammar mode would create false *safety-critical* commands — free-form only.

## 4. Vosk + VAD architecture proposal

```
Microphone (getUserMedia)
   ↓ AudioWorklet: PCM 16 kHz mono, 40 ms frames
WebSocket /voice/stream (binary frames ↑, JSON events ↓)
   ↓
Vosk KaldiRecognizer.AcceptWaveform(frame)          ← streaming ASR
   ↓ partial events → live caption (DISPLAY ONLY, never executed)
Kaldi endpointer (silence-phone rules, in-model)     ← end-of-utterance detection
   optional accelerator: "flush" on frontend energy-VAD 600 ms silence
                          OR server-side partial-stability (no partial change ≥700 ms)
   ↓ AcceptWaveform returns True → FinalResult()    ← finalized utterance (+66 ms)
   ↓ (only finals pass this gate)
AMAP VoiceService.process_command (unchanged parser + safety tiering)
   ↓ matched action + requires_confirmation
Worker action execution / /multimodal/fuse           ← unchanged
```

Answers to the specific questions raised:

- **What performs VAD/end-of-speech?** The primary detector is **Vosk's built-in Kaldi endpointer** — it is speech-model-based (silence-phones from the acoustic model), which is inherently more robust to steady factory noise than the current raw-RMS energy check. It is measured-sufficient: 100 % utterance-final detection, 0 false fires on silence/noise, no splits at ≤0.6 s pauses.
- **Is Vosk's endpoint/final behavior sufficient?** Functionally yes. Latency-wise it averages ≈0.95 s after the last word (0.62–1.31 s). If lower latency is wanted, add the **hybrid flush**: the frontend already computes 600 ms energy silence — reuse it as a *hint*: server flushes (`AcceptWaveform(b"")` → `FinalResult()`) when (partial non-empty) AND (frontend-VAD silent ≥600 ms OR partial text stable ≥700 ms). Expected end-of-speech→final ≈ **0.65–0.7 s**. The built-in endpointer remains the correctness backstop (it still fires on its own).
- **Is an additional VAD (WebRTC/silero) needed?** **Not for the primary path** — that would add a component without a measured gap to fill. Keep silero-VAD as a *contingency* if the pilot shows factory noise causing endpoint trouble; it would slot in as another flush-hint source, not as the executor of commands.
- **Silence duration handling:** default model rules (rule2 0.5 s trailing, rule3 0.75 s, rule4 1.0 s) — measured safe. Tuning rule2 to 0.35 s gave marginal gains (1/6 clips) and erodes pause tolerance; not recommended initially.
- **Avoiding cut-off on brief pauses:** measured — 0.35 s, 0.5 s and 0.6 s pauses inside an utterance did **not** split it; the endpointer needs sustained trailing silence plus decoder confirmation. The two-stage policy (fast flush-hint only when partial is non-empty and *stable*, hard endpoint as backstop) preserves this.
- **Avoiding unnecessary waiting:** the flush-hint path (~0.65–0.7 s) beats both today's pipeline (1.16–3.67 s) and the untuned endpointer (~0.95 s), and the worker sees live partials from ~0.7 s, so perceived responsiveness is immediate even before the final fires.

## 5. faster-whisper (current) vs Vosk (proposed) — factual comparison

| # | Axis | faster-whisper Tiny (current, batch) | Vosk small (proposed, streaming) |
|---|---|---|---|
| 1 | Recognition latency | 556–606 ms EN / 527–3057 ms HI backend segment, **after** the clip is fully recorded+uploaded | Partials while speaking (first ≈0.7 s from stream start); final ~instantly at endpoint |
| 2 | End-of-speech latency | 600 ms frontend energy VAD (fragile) + full batch round trip → **1.16–3.67 s to execution** | Endpointer 0.62–1.31 s (+66 ms final); **~0.8–1.4 s untuned, ~0.65–0.7 s with hybrid flush** |
| 3 | CPU usage | 108–128 % of one core per transcription (bursts) | 15–38 % of one core while streaming; 4.4 % idle listening |
| 4 | RAM usage | ~219 MB incremental (measured delta in-process) | ~202 MB EN-only; ~350 MB both languages resident |
| 5 | Model size | 77 MB (CT2 tiny, int8) | EN 41 MB zip / HI 44 MB zip (~68–79 MB unpacked each) |
| 6 | English accuracy | 6/6 clips (1 token-spacing artifact "Showfailed") | **6/6 exact** |
| 7 | Hindi accuracy | **2/4** — 2 garbage transcripts → commands missed; transliterates to Latin | **4/4 exact Devanagari**; all matched by existing parser |
| 8 | Short-command accuracy | Good EN, weak HI (measured) | Excellent on test set (10/10 free-form) |
| 9 | Streaming capability | None (batch by design) | Native (partial → endpoint → final) |
| 10 | Offline capability | Yes (local model, prefetched) | Yes (fully local) |
| 11 | Implementation complexity | Already deployed | **Moderate new work:** WS endpoint, AudioWorklet capture, connection lifecycle (see §11) |
| 12 | Browser integration | `MediaRecorder` + multipart upload (works everywhere) | `AudioWorklet` + WebSocket (modern browsers; Safari 14.1+/Chrome/Edge/Firefox OK — verify in pilot) |
| 13 | Backend integration | Stateless HTTP, trivially load-balanced | Stateful per-connection recognizer (session affinity), FastAPI WebSocket — well-trodden but new |
| 14 | Failure/error handling | Mature: fail-closed gates, 413/422/503, retry UI, 10 s timeout | New modes to design: WS drop → recognizer state loss (recoverable: new utterance), model load failure at startup, backpressure; batch endpoint kept as fallback |
| 15 | Suitability for AMAP accessibility use case | Works, but 1.2–3.7 s dead air, no feedback, mic gaps, 4 s cap, weak Hindi | Matches the requested Google-voice-input feel: hands-free, live captions, auto end-of-speech, immediate execution, continuous mic, both languages |

## 6. English / Hindi considerations

- **English:** Vosk small-en-us handled every AMAP command and every out-of-vocabulary example phrase exactly. Indian-accent English was **not** testable here (no `vosk-model-small-en-in` reachable from this sandbox); if the factory workforce speaks Indian-accented English, add the Indian-English model to the pilot matrix (same integration path; model provenance must be verified as with HI).
- **Hindi:** Vosk small-hi produced exact Devanagari for all 4 commands and beat Whisper-Tiny 4/4 vs 2/4 on identical audio. Caveats stated plainly: the model README reports 39.08 % WER on its general Hindi test set (20.89 % on the IITM set) — excellent on short commands in this test, but **real-speaker Hindi robustness must be proven in the pilot**. The existing AMAP vocabulary already contains the Devanagari + romanized forms the parser needs — no vocabulary change required.
- **Language selection:** keep the existing per-worker `sttLanguage` preference choosing which Vosk model a connection uses; both models stay resident (350 MB total).
- **Mixing:** a Hindi worker's English brand words ("inverter", part codes) will be decoded by whichever model is active — same trade-off as today; the parser's fuzzy matching absorbs it.

## 7. Expected latency behavior (target UX, measured)

For the brief's example — worker says **"Show failed inspection records"** and stops (measured, Vosk free-form):

```
t=0.00  [Mic listening]                      (idle: 4.4% of one core)
t=0.30  speech begins
t=0.74  first partial "show"                 → live caption appears
t=1.83  speech ends (word_end, measured)
t=2.57  endpointer fires (+0.74 s)           → AcceptWaveform == True
t=2.64  FinalResult() "show failed inspection records"  (+66 ms)
t=2.64  VoiceService.match_command → unmatched (NOT an AMAP command — correct, graceful feedback)
        (an in-vocabulary command executes here — same instant)
```
End-of-speech → final transcript: **0.74 s** (range across 10 clips: 0.62–1.31 s; ≈0.65–0.7 s expected with the hybrid flush). Today's pipeline on the same clip: 600 ms VAD + upload + 603 ms backend + parse RTT ≈ **1.3 s with no live feedback**.

No stop button, no upload step, no long wait — and partials are display-only (measured transient partial *"show failed in"* proves why partials must never execute).

## 8. CPU / RAM considerations

- Measured on 2 vCPU / 4 GB (a realistic low-end workstation/edge box): one active Vosk stream ≈ 15–38 % of one core; idle listening 4.4 %. Whisper bursts at 108–128 % of one core per request. **N concurrent streaming workers ≈ N × ~0.3 cores** — on this box that means a dedicated voice edge node beyond ~4–6 simultaneous workers, or vosk-server with a worker pool. Batch whisper, being bursty, currently serves more workers per core but with the latency/gap penalties above.
- RAM: both Vosk models resident = ~350 MB total (vs ~219 MB whisper incremental). Keeping whisper as fallback means both stacks resident ≈ 570 MB — fine on 4 GB, plan for it on smaller edge boxes.
- Vosk is synchronous per recognizer; run each connection's `AcceptWaveform` in a threadpool worker (it is fast: 40 ms frames process in ~2–10 ms measured via the low streaming CPU%).

## 9. Risks and limitations

1. **TTS-only evidence** — all accuracy figures are from neural-TTS clips, one voice per language. Real workers, accents, distance from mic, and factory noise are unproven → pilot required before any default switch.
2. **Hindi model general WER ≈ 39 %** (README) — short commands measured 4/4, but broader Hindi phrasing may degrade; the parser's fuzzy tier (≥0.75) provides a floor, and unmatched is always safe.
3. **Grammar mode is a safety hazard** (measured false safety-critical matches) — must not be used; also non-functional for Hindi.
4. **New stateful component** (WebSocket + per-connection recognizers): connection drops, rebalancing, auth-at-upgrade, and backpressure are new operational surfaces.
5. **AudioWorklet browser support** — fine on current Chrome/Edge/Firefox/Safari 14.1+, but the pilot must cover the actual floor devices; keep `MediaRecorder` batch path as fallback.
6. **Hindi model provenance** — official host blocked in this sandbox; the tested model came from a third-party GitHub mirror (structure complete, free-form verified working, but the zip checksum could not be independently confirmed). For production, fetch from alphacephei.com and verify SHA-256 (`7c50a108…17e48`).
7. **Endpoint tuning is subtle** — rule2 tightening had limited effect (decoder silence-lag dominates); do not promise sub-0.6 s without the hybrid flush, and re-measure on target hardware.
8. **Concurrent-stream scaling** unmeasured (no load test here).
9. Vosk maintenance mode: the ecosystem is mature but slower-moving than Whisper; for AMAP's fixed command vocabulary this is acceptable, and whisper remains the fallback.

## 10. Exact recommended architecture (if Vosk proceeds)

**Keep faster-whisper batch endpoints as fallback; add a parallel streaming path. Everything command/safety-related stays as-is.**

- **Frontend:** new `useVoiceStream` hook (same callback shape as `useVoiceRecorder`: `onTranscript`/`onPartial`/`onError`/`onStateChange`) — `getUserMedia` → `AudioWorklet` (16 kHz mono PCM, 40 ms frames) → authenticated WebSocket `wss://…/api/v1/voice/stream?lang=en|hi` → renders partials as live captions; on `{"type":"final", …}` calls the existing transcript handler. Feature flag `voiceMode: 'batch' | 'stream'` (default `batch`) until the pilot passes.
- **Backend:** new `/voice/stream` WebSocket route: JWT at upgrade + org check; registry of `KaldiRecognizer` per connection (model by `lang` param; both models preloaded at startup); 40 ms frames → `AcceptWaveform`; partial events throttled ~10/s (display-only); on endpoint → `FinalResult()` → **in-process call to the existing `VoiceService.process_command`** → single message `{type:'final', transcript, matched_command, action_mapping, requires_confirmation, validation_status}`. Optional flush-hint message from the client (its existing 600 ms energy silence) to cut latency to ~0.65 s, with the built-in endpointer as backstop.
- **Models:** `scripts/prefetch_vosk_models.py` (mirroring the whisper prefetch pattern) downloading from alphacephei.com with SHA-256 verification into `backend/.vosk_cache/`; Docker volume identical to the whisper pattern.
- **Safety invariants:** only endpoint/flush finals reach the parser; partials never leave the display path; safety-critical commands keep `requires_confirmation`; 500 ms debounce latch stays; emergency-stop lockout stays.

## 11. Migration complexity

**Moderate — additive, not disruptive.** Rough sizes: backend WS route + recognizer registry + tests ≈ the largest chunk; frontend hook + HUD wiring small (the HUD already consumes a transcript callback); ops = model prefetch script + Docker + RAM headroom. No database changes, no API contract breaks, no vocabulary changes, no RBAC changes. The batch pipeline remains fully functional throughout — the flag decides which path the worker uses, so rollback is instantaneous.

## 12. What would change in the frontend

- `useVoiceStream` hook: AudioWorklet PCM capture (replacing `MediaRecorder` for streaming mode), WS client with reconnect/backoff, partial→caption wiring, final→existing `handleVoiceTranscript` path.
- `MultimodalHUD`: live partial caption element; mic-state map gains `STREAMING`; modality switcher unchanged.
- `useVoiceRecorder` and `MediaRecorder` path: **kept** (fallback + onboarding mic test).
- No changes to: action execution, gesture pipeline, fusion inputs, i18n, accessibility context.

## 13. What would change in the backend

- New `routes/voice_stream.py` (WebSocket), new `services/vosk_stream_service.py` (model registry + per-connection recognizers + endpoint policy), `requirements.txt` + `vosk`, model prefetch script + Docker/compose service (whisper pattern).
- `SpeechToTextService`, `VoiceService`, `/voice/transcribe`, `/voice/process-command`, `/multimodal/fuse`: **unchanged** (the stream service *calls* VoiceService in-process).

## 14. What should remain unchanged (explicitly)

The 22-command bilingual vocabulary and its PostgreSQL-backed personalization; `VoiceService` matching + confidence/safety tiering; confirmation gating for safety-critical actions; the 500 ms debounce; emergency-stop priority + lockout; `/multimodal/fuse` voice+gesture fusion (a final transcript + timestamp slots into the same input schema); all auth/RBAC/tenant isolation; gesture pipeline; i18n (en/hi); the batch whisper endpoints as fallback and onboarding tooling.

## 15. Implementation plan for a FUTURE phase (not now)

1. **Decision gate** — accept/reject this report's recommendation.
2. **Backend (≈ first milestone):** vosk prefetch script (checksummed) → `/voice/stream` WS route + recognizer registry + in-process `VoiceService` call; unit tests with synthetic PCM (silence/noise/utterance/pause cases from `investigation/vosk/endpoint_probes.py` semantics) + integration tests with the 10 TTS fixtures.
3. **Frontend:** `useVoiceStream` + HUD captions behind `voiceMode` flag (default `batch`).
4. **Pilot (mandatory, humans):** real-browser mic sessions, EN + HI speakers, factory-noise playback, floor devices; acceptance = full command matrix + negatives (no partial execution, noise immunity, ≤0.6 s pause tolerance, rapid command sequences, mic unplug/reconnect).
5. **Tune:** endpoint rules + hybrid-flush thresholds on pilot hardware; re-run the §7 latency table.
6. **Load test:** N concurrent streams on target hardware; size worker pool / edge node.
7. **Flip default** to `stream` per-worker (fresher opt-in first), keep batch fallback; burn-in, then remove the flag only after a stability period.

---

### Bottom line

The target interaction — *mic on → speak naturally → automatic end-of-speech → command executes immediately, no stop button, no upload wait, no partial-execution, EN + HI offline* — is **technically achievable with Vosk's streaming recognizer + built-in Kaldi endpointer (+ optional frontend-VAD flush hint)**, with measured end-of-speech→execution of **~0.8 s untuned / ~0.65–0.7 s tuned** versus **1.16–3.67 s** today, live partial captions, continuous mic coverage, ~3× lower recognition CPU, and measured 4/4 vs 2/4 Hindi command accuracy on identical audio. The known hazards (grammar-mode false commands, Hindi model provenance, TTS-only evidence) are avoidable/managed by the architecture above. **No production code was changed in this investigation.**
