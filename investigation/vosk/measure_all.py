#!/usr/bin/env python3
"""Master measurement harness: Vosk streaming vs current faster-whisper batch.

All measurements real, in-process:
- Vosk EN (free-form + AMAP grammar) on 6 EN clips, real-time chunk feeding
- Vosk HI (free-form + Hindi grammar) on 4 HI clips
- Continuous two-utterance stream (re-arm after endpoint)
- Production SpeechToTextService (faster-whisper tiny int8, ffmpeg decode)
  on webm-encoded variants of the SAME clips (browser-identical path)
- Real AMAP VoiceService.match_command applied to every engine output
Outputs JSON to /tmp/vosk_tests/results.json
"""
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import psutil
from vosk import Model, KaldiRecognizer, SetLogLevel

sys.path.insert(0, "/home/user/AMAP/backend")
from services.voice_service import VoiceService  # real AMAP parser (read-only import)

SetLogLevel(-1)

FF = "/tmp/amapvoice/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
RATE = 16000
AUDIO = Path("/tmp/vosk_tests/audio")
PROC = psutil.Process()
OUT = {"vosk": {}, "whisper": {}, "continuous": {}, "parse": {}}

EN_CLIPS = ["en_next_step", "en_go_back", "en_emergency_stop", "en_show_failed",
            "en_submit_result", "en_open_production"]
HI_CLIPS = ["hi_agla_kadam", "hi_madad", "hi_roko", "hi_radd_karein"]

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
AMAP_HI_GRAMMAR = json.dumps([
    "अगला", "आगे", "अगला कदम", "पिछला", "वापस",
    "पुष्टि", "हाँ", "सही",
    "रद्द करें",
    "विराम",
    "फिर से शुरू",
    "मदद", "सहायता",
    "आपातकाल", "रोकें", "रुको",
    "क्लिक",
    "उठाओ", "छोड़ो", "चुनो",
    "काम शुरू करो",
])


import numpy as np

def to16k(name):
    """Resample a TTS clip to 16 kHz mono PCM.
    - vosk feed: +1.5s trailing silence (mic stays open; endpointer decides)
    - webm (whisper, current frontend behavior): +0.6s trailing silence
    """
    src = AUDIO / f"{name}.wav"
    wav16 = AUDIO / f"{name}_16k.wav"
    webm = AUDIO / f"{name}.webm"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(src),
                    "-ar", str(RATE), "-ac", "1", str(wav16)], check=True)
    with wave.open(str(wav16), "rb") as w:
        arr = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    padded = np.concatenate([arr, np.zeros(int(RATE * 1.5), dtype=np.int16)])
    # webm variant: speech + 0.6s silence (what useVoiceRecorder uploads today)
    wav_pad = AUDIO / f"{name}_pad06.wav"
    with wave.open(str(wav_pad), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(np.concatenate([arr, np.zeros(int(RATE * 0.6), dtype=np.int16)]).tobytes())
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(wav_pad),
                    "-c:a", "libopus", "-b:a", "32k", str(webm)], check=True)
    return padded.tobytes(), len(arr) / RATE


def feed(rec, pcm_bytes, chunk_ms=40):
    """Real-time paced feed. Returns dict with partials/endpoint/final timings."""
    events = {"first_partial_at": None, "partials": [], "endpoint_at": None,
              "final": None, "word_end": None, "conf": None}
    chunk = int(RATE * 2 * chunk_ms / 1000)
    t0 = time.perf_counter()
    audio_t = 0.0
    i = 0
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
            events["endpoint_at"] = time.perf_counter() - t0
            break
        p = json.loads(rec.PartialResult()).get("partial", "")
        if p:
            if events["first_partial_at"] is None:
                events["first_partial_at"] = time.perf_counter() - t0
            if not events["partials"] or events["partials"][-1] != p:
                events["partials"].append(p)
    final = json.loads(rec.FinalResult())
    events["final"] = final.get("text", "")
    words = final.get("result") or []
    if words:
        events["word_end"] = words[-1].get("end")
        events["conf"] = round(sum(w.get("conf", 0) for w in words) / len(words), 3)
    return events


def cpu_pct(fn):
    """Run fn() measuring wall time, process CPU time, RSS delta."""
    ct0 = PROC.cpu_times()
    rss0 = PROC.memory_info().rss
    t0 = time.perf_counter()
    out = fn()
    wall = time.perf_counter() - t0
    ct1 = PROC.cpu_times()
    cpu = (ct1.user - ct0.user) + (ct1.system - ct0.system)
    return out, {"wall_s": round(wall, 3), "cpu_s": round(cpu, 3),
                 "cpu_util_pct_of_core": round(cpu / wall * 100, 1) if wall else None,
                 "rss_delta_mb": round((PROC.memory_info().rss - rss0) / 1e6, 1)}


# ---------------------------------------------------------------- Vosk EN
print("== loading Vosk EN model ==", flush=True)
t0 = time.perf_counter()
model_en = Model("/tmp/vosk-models/vosk-model-small-en-us-0.15")
OUT["vosk"]["en_load_s"] = round(time.perf_counter() - t0, 2)
OUT["vosk"]["en_rss_after_load_mb"] = round(PROC.memory_info().rss / 1e6, 0)
print(f"load {OUT['vosk']['en_load_s']}s rss {OUT['vosk']['en_rss_after_load_mb']}MB")

t0 = time.perf_counter()
model_hi = Model("/tmp/vosk-hi-repo/vosk/vosk-model-small-hi-0.22")
OUT["vosk"]["hi_load_s"] = round(time.perf_counter() - t0, 2)
OUT["vosk"]["both_models_rss_mb"] = round(PROC.memory_info().rss / 1e6, 0)
print(f"hi load {OUT['vosk']['hi_load_s']}s rss(both) {OUT['vosk']['both_models_rss_mb']}MB")

pcm16k = {}
durs = {}
for name in EN_CLIPS + HI_CLIPS:
    pcm16k[name], durs[name] = to16k(name)
print("clips resampled:", {k: round(v, 2) for k, v in durs.items()})

for name in EN_CLIPS:
    row = {}
    rec = KaldiRecognizer(model_en, RATE); rec.SetWords(True)
    ev, perf = cpu_pct(lambda: feed(rec, pcm16k[name]))
    if ev["endpoint_at"] is not None and ev["word_end"] is not None:
        ev["endpoint_latency_after_speech_end_s"] = round(ev["endpoint_at"] - ev["word_end"], 3)
    row["freeform"] = {**ev, "dur_s": round(durs[name], 2), **perf}
    rec = KaldiRecognizer(model_en, RATE, AMAP_EN_GRAMMAR)
    ev2, perf2 = cpu_pct(lambda: feed(rec, pcm16k[name]))
    row["grammar"] = {**ev2, **perf2}
    OUT["vosk"][name] = row
    print(f"{name}: freeform final={row['freeform']['final']!r} endpoint={row['freeform']['endpoint_at']}s "
          f"word_end={row['freeform']['word_end']}s | grammar final={row['grammar']['final']!r}", flush=True)

for name in HI_CLIPS:
    row = {}
    rec = KaldiRecognizer(model_hi, RATE); rec.SetWords(True)
    ev, perf = cpu_pct(lambda: feed(rec, pcm16k[name]))
    if ev["endpoint_at"] is not None and ev["word_end"] is not None:
        ev["endpoint_latency_after_speech_end_s"] = round(ev["endpoint_at"] - ev["word_end"], 3)
    row["freeform"] = {**ev, "dur_s": round(durs[name], 2), **perf}
    rec = KaldiRecognizer(model_hi, RATE, AMAP_HI_GRAMMAR)
    ev2, perf2 = cpu_pct(lambda: feed(rec, pcm16k[name]))
    row["grammar"] = {**ev2, **perf2}
    OUT["vosk"][name] = row
    print(f"{name}: freeform final={row['freeform']['final']!r} | grammar final={row['grammar']['final']!r}", flush=True)

# ------------------------------------------- continuous 2-utterance stream
import numpy as np
def cat(*arrs):
    return np.concatenate(arrs).tobytes()
a = np.frombuffer(pcm16k["en_show_failed"], dtype=np.int16)
b = np.frombuffer(pcm16k["en_next_step"], dtype=np.int16)
gap = np.zeros(int(RATE * 0.9), dtype=np.int16)
stream = cat(a, gap, b, np.zeros(int(RATE * 2), dtype=np.int16))
rec = KaldiRecognizer(model_en, RATE)  # FREE-FORM (recommended architecture)
rec.SetWords(True)
utterances = []
chunk = int(RATE * 2 * 0.04)
t0 = time.perf_counter()
audio_t = 0.0
i = 0
pending = None
while i < len(stream):
    data = stream[i:i + chunk]; i += chunk
    chunk_dur = len(data) / (2 * RATE)
    target = t0 + audio_t + chunk_dur
    now = time.perf_counter()
    if target > now:
        time.sleep(target - now)
    audio_t += chunk_dur
    if rec.AcceptWaveform(data):
        final = json.loads(rec.FinalResult()).get("text", "")
        utterances.append({"at_s": round(time.perf_counter() - t0, 3),
                           "final": final,
                           "gap_since_prev_endpoint": None})
        if pending:
            utterances[-1]["gap_since_prev_endpoint"] = round(utterances[-1]["at_s"] - pending, 3)
        pending = utterances[-1]["at_s"]
OUT["continuous"] = {"utterances": utterances, "stream_len_s": round(len(stream) / (2 * RATE), 2)}
print("continuous stream utterances:", utterances)

# ------------------------------------------- current production whisper
from services.speech_to_text_service import SpeechToTextService
svc = SpeechToTextService()

def wh_run(name, lang):
    webm_bytes = (AUDIO / f"{name}.webm").read_bytes()
    t0 = time.perf_counter()
    res = svc.transcribe(webm_bytes, language=lang, filename="clip.webm")
    wall = time.perf_counter() - t0
    return {"transcript": res.transcript, "detected_language": res.detected_language,
            "confidence": res.confidence, "backend_processing_time_ms": res.processing_time_ms,
            "measured_wall_s": round(wall, 3)}

# cold load (first transcribe triggers model load)
print("\n== whisper cold start (first transcribe loads model) ==", flush=True)
ct0 = PROC.cpu_times(); rss0 = PROC.memory_info().rss
t0 = time.perf_counter()
cold = wh_run("en_next_step", "en")
cold_load_s = time.perf_counter() - t0
ct1 = PROC.cpu_times()
OUT["whisper"]["cold_first_transcribe_s"] = round(cold_load_s, 2)
OUT["whisper"]["rss_after_model_mb"] = round(PROC.memory_info().rss / 1e6, 0)
print(f"cold first transcribe (incl model load): {cold_load_s:.2f}s -> {cold['transcript']!r}")

for name, lang in ([(n, "en") for n in EN_CLIPS] + [(n, "hi") for n in HI_CLIPS]):
    ct0 = PROC.cpu_times(); rss0 = PROC.memory_info().rss
    t0 = time.perf_counter()
    res = wh_run(name, lang)
    wall = time.perf_counter() - t0
    ct1 = PROC.cpu_times()
    cpu = (ct1.user - ct0.user) + (ct1.system - ct0.system)
    OUT["whisper"][name] = {**res,
                            "cpu_s": round(cpu, 3),
                            "cpu_util_pct_of_core": round(cpu / wall * 100, 1),
                            "rss_delta_mb": round((PROC.memory_info().rss - rss0) / 1e6, 1)}
    print(f"{name} ({lang}): {res['transcript']!r} backend={res['backend_processing_time_ms']}ms wall={wall:.2f}s", flush=True)

# ------------------------------------------- real AMAP parser on all outputs
vs = VoiceService()
def parse(text):
    m = vs.match_command(text)
    return {"matched": m[0], "action": m[1], "score": m[2], "safety_critical": m[3]}

for name in EN_CLIPS + HI_CLIPS:
    OUT["parse"][name] = {
        "vosk_freeform": {"text": OUT["vosk"][name]["freeform"]["final"],
                          **parse(OUT["vosk"][name]["freeform"]["final"])},
        "vosk_grammar": {"text": OUT["vosk"][name]["grammar"]["final"],
                         **parse(OUT["vosk"][name]["grammar"]["final"])},
        "whisper": {"text": OUT["whisper"][name]["transcript"],
                    **parse(OUT["whisper"][name]["transcript"])},
    }
    print(f"PARSE {name}: vosk={OUT['parse'][name]['vosk_freeform']['matched']} "
          f"grammar={OUT['parse'][name]['vosk_grammar']['matched']} "
          f"whisper={OUT['parse'][name]['whisper']['matched']}")

Path("/tmp/vosk_tests/results2.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1))
print("\nresults -> /tmp/vosk_tests/results2.json")
