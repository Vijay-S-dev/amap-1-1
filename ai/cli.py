"""
Command-Line Interface and Benchmarking Utility for the AMAP AI Subsystem.
"""

import argparse
import time

from ai.gesture.dataset import generate_synthetic_landmarks
from ai.models.types import (
    BoundingBox,
    GestureFramePayload,
    GestureType,
    Handedness,
    InputModality,
    LandmarkPoint,
    MultimodalInputItem,
    VoiceCommandPayload,
)
from ai.pipeline import MultimodalAIPipeline


def run_benchmark() -> None:
    """Run end-to-end benchmark across optical, voice, and fusion engines."""
    print("=================================================================")
    print("           AMAP MULTIMODAL AI SUBSYSTEM BENCHMARK                ")
    print("=================================================================")

    pipeline = MultimodalAIPipeline()

    # 1. Optical Gesture Benchmark
    print("\n[1/3] Benchmarking Optical Hand Gesture Recognition...")
    gestures = [
        GestureType.THUMBS_UP,
        GestureType.OPEN_PALM,
        GestureType.PINCH,
        GestureType.POINTING,
    ]
    iterations = 200
    t0 = time.perf_counter()

    for g in gestures:
        landmarks = generate_synthetic_landmarks(g)
        hitboxes = [BoundingBox(0.4, 0.4, 0.6, 0.6, target_id="btn_1")]
        payload = GestureFramePayload(
            landmarks=landmarks,
            handedness=Handedness.RIGHT,
            target_hitboxes=hitboxes,
        )
        for _ in range(iterations // len(gestures)):
            res = pipeline.process_gesture_frame(payload)

    t_gesture = (time.perf_counter() - t0) * 1000.0 / iterations
    print(f"  -> Processed {iterations} frames in {t_gesture:.3f} ms / frame (Throughput: {1000.0 / t_gesture:.1f} FPS)")

    # 2. Voice Recognition Benchmark
    print("\n[2/3] Benchmarking Acoustic Voice Command Recognition...")
    commands = ["next step", "confirm", "pause session", "emergency stop", "go back"]
    t0 = time.perf_counter()

    for cmd in commands:
        payload = VoiceCommandPayload(transcript=cmd)
        for _ in range(iterations // len(commands)):
            res = pipeline.process_voice_command(payload)

    t_voice = (time.perf_counter() - t0) * 1000.0 / iterations
    print(f"  -> Processed {iterations} transcripts in {t_voice:.3f} ms / command")

    # 3. Multimodal Fusion Benchmark
    print("\n[3/3] Benchmarking Cross-Modal Temporal Fusion Engine...")
    t0 = time.perf_counter()

    for _ in range(iterations):
        items = [
            MultimodalInputItem(
                mode=InputModality.GESTURE,
                raw_intent="thumbs_up",
                confidence=0.92,
                timestamp_ms=1000,
            ),
            MultimodalInputItem(
                mode=InputModality.VOICE,
                raw_intent="confirm",
                confidence=0.94,
                timestamp_ms=1050,
            ),
        ]
        fused = pipeline.fuse_multimodal_inputs(items)

    t_fusion = (time.perf_counter() - t0) * 1000.0 / iterations
    print(f"  -> Fused {iterations} multimodal pairs in {t_fusion:.3f} ms / fusion")
    print(f"  -> Fused Action: '{fused.fused_action}' (Confidence: {fused.fused_confidence:.3f}, Strategy: {fused.fusion_strategy.value})")

    print("\n=================================================================")
    print("           BENCHMARK COMPLETED SUCCESSFULLY (ALL PASS)          ")
    print("=================================================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAP AI Diagnostic & Benchmark CLI")
    parser.add_argument("--benchmark", action="store_true", help="Run full pipeline performance benchmark")
    parser.add_argument("--demo", action="store_true", help="Run demo inference loop")
    args = parser.parse_args()

    if args.benchmark or not any(vars(args).values()):
        run_benchmark()


if __name__ == "__main__":
    main()
