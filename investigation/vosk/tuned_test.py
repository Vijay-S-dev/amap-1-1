#!/usr/bin/env python3
"""Tuned endpointer (rule2.min-trailing-silence=0.35) vs default (0.5):
endpoint latency on all EN clips + cut-off risk on pause probes + noise probes."""
import json
import time
import wave
from pathlib import Path

import numpy as np
from vosk import Model, KaldiRecognizer, SetLogLevel

SetLogLevel(-1)
RATE = 16000
AUDIO = Path("/tmp/vosk_tests/audio")
EN_CLIPS = ["en_next_step", "en_go_back", "en_emergency_stop", "en_show_failed",
            "en_submit_result", "en_open_production"]

def pcm16k(name):
    with wave.open(str(AUDIO / f"{name}_16k.wav"), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

def feed(rec, pcm_bytes, chunk_ms=40):
    out = {"endpoint_at": None, "final": None, "word_end": None}
    chunk = int(RATE * 2 * chunk_ms / 1000)
    t0 = time.perf_counter()
    audio_t = 0.0
    i = 0
    partials = []
    while i < len(pcm_bytes):
        data = pcm_bytes[i:i + chunk]
        i += chunk
        chunk_dur = len(data) / (2 * RATE)
        target = t0 + audio_t + chunk_dur
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        audio_t += chunk_dur
        if rec.AcceptWaveform(data):
            out["endpoint_at"] = round(time.perf_counter() - t0, 3)
            break
        p = json.loads(rec.PartialResult()).get("partial", "")
        if p and (not partials or partials[-1] != p):
            partials.append(p)
    fr = json.loads(rec.FinalResult())
    out["final"] = fr.get("text", "")
    words = fr.get("result") or []
    if words:
        out["word_end"] = words[-1].get("end")
    out["partials"] = partials
    if out["endpoint_at"] and out["word_end"]:
        out["endpoint_latency_after_speech_end_s"] = round(out["endpoint_at"] - out["word_end"], 3)
    return out

results = {}
for label, path in [("default_0.5", "/tmp/vosk-models/vosk-model-small-en-us-0.15"),
                    ("tuned_0.35", "/tmp/vosk-models/en-tuned")]:
    model = Model(path)
    results[label] = {}
    for name in EN_CLIPS:
        arr = pcm16k(name)
        stream = np.concatenate([arr, np.zeros(int(RATE * 1.5), dtype=np.int16)]).tobytes()
        rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
        results[label][name] = feed(rec, stream)
        r = results[label][name]
        print(f"[{label}] {name}: final={r['final']!r} endpoint_latency={r.get('endpoint_latency_after_speech_end_s')}s")

    # cut-off risk: 0.35s and 0.5s pauses inserted inside 'next step'
    arr = pcm16k("en_next_step")
    first = arr[:int(RATE * 0.45)]
    rest = arr[int(RATE * 0.45):]
    for pause in (0.35, 0.5):
        stream = np.concatenate([first, np.zeros(int(RATE * pause), dtype=np.int16),
                                 rest, np.zeros(int(RATE * 1.2), dtype=np.int16)]).tobytes()
        rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
        r = feed(rec, stream)
        results[label][f"pause_{pause}s_inside"] = r
        print(f"[{label}] pause {pause}s inside utterance -> final={r['final']!r} (split/cut-off: {r['final'] != 'next step'})")

    # noise: must not endpoint with a command
    rng = np.random.default_rng(42)
    noise = (rng.normal(0, 3000, RATE * 3)).astype(np.int16).tobytes()
    rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
    r = feed(rec, noise)
    results[label]["loud_noise_3s"] = r
    print(f"[{label}] loud noise 3s -> endpoint={r['endpoint_at']} final={r['final']!r}")

Path("/tmp/vosk_tests/tuned_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
print("saved -> /tmp/vosk_tests/tuned_results.json")
