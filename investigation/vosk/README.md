# Vosk feasibility investigation artifacts (NON-PRODUCTION)

Supporting material for /VOSK_VOICE_FEASIBILITY_REPORT.md. Nothing here is used
by the AMAP application. Scripts were run in an isolated venv against the
read-only production service classes.

- endpoint_probes.py  — endpointer robustness probes (silence/noise/pauses/grammar)
- measure_all.py      — master harness: Vosk EN+HI vs production SpeechToTextService
                        (faster-whisper tiny) on identical TTS clips; real
                        VoiceService parsing of every output; continuous re-arm test
- tuned_test.py       — endpointer rule2 0.5s -> 0.35s tuning experiment
- probe_results.json / results2.json / tuned_results.json — raw measured data
- audio/              — the 10 neural-TTS command clips (6 EN, 4 HI) used as stimuli

Environment: 2 vCPU / ~4GB sandbox, vosk 0.3.45, faster-whisper 1.1.0 (int8 CPU),
models vosk-model-small-en-us-0.15 (SHA-256 verified) and vosk-model-small-hi-0.22
(third-party mirror; official host unreachable from the sandbox).

Reproduce: create a venv with `pip install vosk faster-whisper==1.1.0 psutil
imageio-ffmpeg numpy` + backend/requirements.txt, place the two Vosk models at
/tmp/vosk-models/... and /tmp/vosk-hi-repo/... (or edit the paths), rebuild the
whisper cache with scripts/prefetch_whisper_model.py, then run the scripts.
