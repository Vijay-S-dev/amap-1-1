#!/usr/bin/env python3
"""Idle-listening CPU + FinalResult latency (folded into report section 3/8)."""
import time, json
import numpy as np
import psutil
from vosk import Model, KaldiRecognizer, SetLogLevel
SetLogLevel(-1)
RATE = 16000
proc = psutil.Process()
model = Model("/tmp/vosk-models/vosk-model-small-en-us-0.15")
rec = KaldiRecognizer(model, RATE)
silence = np.zeros(RATE * 10, dtype=np.int16).tobytes()
chunk = int(RATE * 2 * 0.04)
ct0 = proc.cpu_times(); t0 = time.perf_counter()
i = 0; audio_t = 0.0
while i < len(silence):
    data = silence[i:i+chunk]; i += chunk
    target = t0 + audio_t + 0.04
    now = time.perf_counter()
    if target > now: time.sleep(target - now)
    audio_t += 0.04
    rec.AcceptWaveform(data)
ct1 = proc.cpu_times()
cpu = (ct1.user - ct0.user) + (ct1.system - ct0.system)
wall = time.perf_counter() - t0
print(f"idle listening 10s: cpu_s={cpu:.3f} wall_s={wall:.1f} -> {cpu/wall*100:.1f}% of one core")
