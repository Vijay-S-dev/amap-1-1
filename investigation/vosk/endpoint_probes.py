#!/usr/bin/env python3
"""Robustness probes for the Vosk endpointer (no TTS speech needed).
Writes results to /tmp/vosk_tests/probe_results.json as well as stdout."""
import json
import time
import wave

import numpy as np
from vosk import Model, KaldiRecognizer, SetLogLevel

SetLogLevel(-1)
MODEL_EN = "/tmp/vosk-models/vosk-model-small-en-us-0.15"
RATE = 16000
FIXTURE = "/tmp/vosk_tests/next_step_16k.wav"  # SAPI voice "next step", speech 0.09-0.9s

AMAP_EN_GRAMMAR = json.dumps([
    "next", "next step", "continue", "proceed", "forward", "advance",
    "previous", "previous step", "back", "go back",
    "confirm", "confirm action", "confirm this", "yes", "approve", "ok", "okay", "accept",
    "cancel", "cancel action", "no", "reject", "abort",
    "pause", "pause session", "hold on", "standby",
    "resume", "resume session",
    "help", "call supervisor", "assistance", "need help", "i need help",
    "emergency", "emergency stop", "shut down", "halt", "stop",
    "left click", "click", "click this", "click here", "press", "tap",
    "right click", "double click", "double tap",
    "drag", "drag this", "grab", "pick up",
    "drop", "drop it", "release",
    "select", "select this", "select item", "choose this",
    "scroll up", "scroll down", "scroll left", "scroll right",
    "page up", "page down",
    "start task", "start work", "begin work",
    "complete step", "complete this step", "step complete", "step done", "finish step",
    "finish task", "finish assignment", "end work", "complete task",
])

def pcm(wave_path):
    wf = wave.open(wave_path, "rb")
    return wf.readframes(wf.getnframes())

def feed_realtime(rec, pcm_bytes, chunk_ms=40):
    events = []
    chunk = int(RATE * 2 * chunk_ms / 1000)
    t0 = time.perf_counter()
    audio_t = 0.0
    endpoint_t = None
    i = 0
    while i < len(pcm_bytes):
        data = pcm_bytes[i:i+chunk]
        i += chunk
        chunk_dur = len(data) / (2 * RATE)
        target = t0 + audio_t + chunk_dur
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        audio_t += chunk_dur
        if rec.AcceptWaveform(data):
            endpoint_t = time.perf_counter() - t0
            events.append(("ENDPOINT", round(endpoint_t, 3)))
            events.append(("FINAL", json.loads(rec.FinalResult()).get("text", "")))
            break
        else:
            p = json.loads(rec.PartialResult()).get("partial", "")
            if p and (not events or (events[-1][0] != "PARTIAL" and events[-1][1] != p)):
                if not events or events[-1][1] != p:
                    events.append(("PARTIAL", p))
    if endpoint_t is None:
        rec.AcceptWaveform(b"")
        events.append(("FLUSH_FINAL", json.loads(rec.FinalResult()).get("text", "")))
    return events

results = {}
t0 = time.perf_counter()
model = Model(MODEL_EN)
results["load_s"] = round(time.perf_counter() - t0, 2)

fixture = pcm(FIXTURE)
silence = np.zeros(RATE * 3, dtype=np.int16)
rng = np.random.default_rng(42)
noise_low = (rng.normal(0, 300, RATE * 3)).astype(np.int16)
noise_high = (rng.normal(0, 3000, RATE * 3)).astype(np.int16)

rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["silence_freeform"] = feed_realtime(rec, silence.tobytes())
rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["noise_low_freeform"] = feed_realtime(rec, noise_low.tobytes())
rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["noise_high_freeform"] = feed_realtime(rec, noise_high.tobytes())

arr = np.frombuffer(fixture, dtype=np.int16)
stream = np.concatenate([arr, np.zeros(int(RATE*0.3), dtype=np.int16), arr, np.zeros(int(RATE*1.2), dtype=np.int16)])
rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["double_utterance"] = feed_realtime(rec, stream.tobytes())

first_word = arr[:int(RATE*0.45)]
rest = arr[int(RATE*0.45):]
with_pause = np.concatenate([first_word, np.zeros(int(RATE*0.35), dtype=np.int16), rest, np.zeros(int(RATE*1.0), dtype=np.int16)])
rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["pause_035s_inside_utterance"] = feed_realtime(rec, with_pause.tobytes())

with_pause2 = np.concatenate([first_word, np.zeros(int(RATE*0.6), dtype=np.int16), rest, np.zeros(int(RATE*1.0), dtype=np.int16)])
rec = KaldiRecognizer(model, RATE); rec.SetWords(True)
results["pause_060s_inside_utterance"] = feed_realtime(rec, with_pause2.tobytes())

rec = KaldiRecognizer(model, RATE, AMAP_EN_GRAMMAR)
results["grammar_fixture"] = feed_realtime(rec, fixture)
rec = KaldiRecognizer(model, RATE, AMAP_EN_GRAMMAR)
results["grammar_silence"] = feed_realtime(rec, silence.tobytes())
rec = KaldiRecognizer(model, RATE, AMAP_EN_GRAMMAR)
results["grammar_noise_high"] = feed_realtime(rec, noise_high.tobytes())

print(json.dumps(results, ensure_ascii=False, indent=1))
with open("/tmp/vosk_tests/probe_results.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("saved -> /tmp/vosk_tests/probe_results.json")
