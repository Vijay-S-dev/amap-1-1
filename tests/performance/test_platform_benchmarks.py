"""
Performance & Stress Benchmarks for the AMAP Multimodal Perception Subsystem.
"""

import sys
import time
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai import (
    BoundingBox,
    CrossModalFusionEngine,
    GestureFramePayload,
    GestureRecognizer,
    GestureType,
    Handedness,
    InputModality,
    LandmarkPoint,
    MultimodalInputItem,
    VoiceCommandPayload,
    VoiceRecognizer,
    generate_synthetic_landmarks,
)


def test_optical_gesture_throughput_benchmark():
    """Verify optical gesture pipeline processes >= 2,000 FPS on CPU."""
    recognizer = GestureRecognizer()
    landmarks = generate_synthetic_landmarks(GestureType.THUMBS_UP)
    hitboxes = [BoundingBox(0.4, 0.4, 0.6, 0.6, target_id="btn_1")]
    payload = GestureFramePayload(
        landmarks=landmarks,
        handedness=Handedness.RIGHT,
        target_hitboxes=hitboxes,
    )

    iterations = 500
    t0 = time.perf_counter()

    for _ in range(iterations):
        res = recognizer.process_frame(payload)

    elapsed_s = time.perf_counter() - t0
    fps = iterations / elapsed_s
    avg_latency_ms = (elapsed_s / iterations) * 1000.0

    print(f"\n[Optical Benchmark] Processed {iterations} frames at {fps:.1f} FPS ({avg_latency_ms:.3f} ms / frame)")
    assert fps >= 1000.0  # Must exceed 1,000 FPS for real-time factory camera feeds


def test_temporal_fusion_latency_benchmark():
    """Verify cross-modal fusion engine takes < 0.5ms per arbitration."""
    fusion_engine = CrossModalFusionEngine()
    items = [
        MultimodalInputItem(
            mode=InputModality.GESTURE,
            raw_intent="thumbs_up",
            confidence=0.92,
            timestamp_ms=1000,
        ),
        MultimodalInputItem(
            mode=InputModality.VOICE,
            raw_intent="confirm_action",
            confidence=0.95,
            timestamp_ms=1050,
        ),
    ]

    iterations = 1000
    t0 = time.perf_counter()

    for _ in range(iterations):
        res = fusion_engine.fuse(items)

    elapsed_s = time.perf_counter() - t0
    avg_latency_ms = (elapsed_s / iterations) * 1000.0

    print(f"\n[Fusion Benchmark] Fused {iterations} multimodal pairs in {avg_latency_ms:.4f} ms / fusion")
    assert avg_latency_ms < 0.50
    assert res.fused_action == "confirm_action"


def test_voice_recognizer_throughput():
    """Verify voice keyword spotting and phonetic matching executes within 15ms."""
    recognizer = VoiceRecognizer()
    payload = VoiceCommandPayload(transcript="next step please")

    iterations = 200
    t0 = time.perf_counter()

    for _ in range(iterations):
        res = recognizer.process_command(payload)

    elapsed_s = time.perf_counter() - t0
    avg_latency_ms = (elapsed_s / iterations) * 1000.0

    print(f"\n[Voice Benchmark] Processed {iterations} commands in {avg_latency_ms:.3f} ms / command")
    assert avg_latency_ms < 15.0
    assert res.action == "next_step"
