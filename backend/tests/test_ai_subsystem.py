"""
Comprehensive Automated Test Suite for the AMAP AI Subsystem.

Tests all optical gesture recognition, acoustic voice command processing,
cross-modal temporal fusion, safety interlock gating, and evidence-based personalization.
"""

import math
import sys
from pathlib import Path
import pytest

# Ensure root AMAP directory is in sys.path so 'ai' is importable
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai import (
    AIAssistant,
    AIService,
    AcousticFeatures,
    AcousticNoiseFilter,
    AdaptationEngine,
    BoundingBox,
    CrossModalFusionEngine,
    DifficultyPatternAnalyzer,
    DwellAccumulator,
    DwellStatus,
    FusionStrategy,
    GeometricClassifier,
    GestureFramePayload,
    GestureRecognizer,
    GestureType,
    Handedness,
    InputModality,
    InteractionEventRecord,
    LandmarkPoint,
    ModelRegistry,
    MultimodalAIPipeline,
    MultimodalInputItem,
    SafetyInterlockEvaluator,
    SpatialTargetDetector,
    VoiceCommandPayload,
    VoiceRecognizer,
    calculate_angle_deg,
    calculate_jitter,
    compute_hand_bounding_box,
    compute_palm_center,
    compute_soundex,
    euclidean_distance_2d,
    euclidean_distance_3d,
    extract_acoustic_features,
    generate_synthetic_landmarks,
    is_voice_active,
    normalize_transcript,
)


# ===========================================================================
# 1. Landmark Geometry & Math Tests
# ===========================================================================

def test_euclidean_distance_2d_and_3d():
    p1 = LandmarkPoint(0.0, 0.0, 0.0)
    p2 = LandmarkPoint(3.0, 4.0, 0.0)
    p3 = LandmarkPoint(0.0, 0.0, 5.0)

    assert math.isclose(euclidean_distance_2d(p1, p2), 5.0)
    assert math.isclose(euclidean_distance_3d(p1, p2), 5.0)
    assert math.isclose(euclidean_distance_3d(p1, p3), 5.0)


def test_calculate_angle_deg():
    # Right angle: (1, 0) -> (0, 0) -> (0, 1)
    a = LandmarkPoint(1.0, 0.0, 0.0)
    b = LandmarkPoint(0.0, 0.0, 0.0)
    c = LandmarkPoint(0.0, 1.0, 0.0)

    angle = calculate_angle_deg(a, b, c)
    assert math.isclose(angle, 90.0, rel_tol=1e-3)


def test_compute_palm_center():
    landmarks = [LandmarkPoint(0.5, 0.5, 0.0) for _ in range(21)]
    palm = compute_palm_center(landmarks)
    assert math.isclose(palm.x, 0.5)
    assert math.isclose(palm.y, 0.5)


def test_compute_hand_bounding_box():
    landmarks = [
        LandmarkPoint(0.2, 0.3, 0.0),
        LandmarkPoint(0.8, 0.7, 0.0),
    ]
    bbox = compute_hand_bounding_box(landmarks, padding=0.05)
    assert bbox.x_min <= 0.2
    assert bbox.x_max >= 0.8
    assert bbox.y_min <= 0.3
    assert bbox.y_max >= 0.7


# ===========================================================================
# 2. Optical Gesture Classification & Dwell Tests
# ===========================================================================

def test_geometric_classifier_synthetic_gestures():
    classifier = GeometricClassifier()

    # Thumbs Up
    tu_pts = generate_synthetic_landmarks(GestureType.THUMBS_UP)
    g, conf = classifier.predict(tu_pts)
    assert g == GestureType.THUMBS_UP
    assert conf >= 0.80

    # Open Palm
    op_pts = generate_synthetic_landmarks(GestureType.OPEN_PALM)
    g, conf = classifier.predict(op_pts)
    assert g == GestureType.OPEN_PALM
    assert conf >= 0.80

    # Pinch
    pinch_pts = generate_synthetic_landmarks(GestureType.PINCH)
    g, conf = classifier.predict(pinch_pts)
    assert g == GestureType.PINCH
    assert conf >= 0.70

    # Pointing
    pt_pts = generate_synthetic_landmarks(GestureType.POINTING)
    g, conf = classifier.predict(pt_pts)
    assert g == GestureType.POINTING
    assert conf >= 0.75


def test_dwell_accumulator_state_machine():
    dwell = DwellAccumulator(dwell_time_ms=400, cooldown_ms=200)
    pt = LandmarkPoint(0.5, 0.5, 0.0)

    # 1. First frame -> DWELLING starts
    status, progress = dwell.update(GestureType.THUMBS_UP, pt, timestamp_ms=1000)
    assert status == DwellStatus.DWELLING
    assert progress == 0.0

    # 2. Intermediate frame at 200ms -> DWELLING 50%
    status, progress = dwell.update(GestureType.THUMBS_UP, pt, timestamp_ms=1200)
    assert status == DwellStatus.DWELLING
    assert math.isclose(progress, 0.5, rel_tol=1e-2)

    # 3. Trigger frame at 400ms -> TRIGGERED 100%
    status, progress = dwell.update(GestureType.THUMBS_UP, pt, timestamp_ms=1400)
    assert status == DwellStatus.TRIGGERED
    assert progress == 1.0

    # 4. Immediate subsequent frame -> COOLDOWN
    status, progress = dwell.update(GestureType.THUMBS_UP, pt, timestamp_ms=1450)
    assert status == DwellStatus.COOLDOWN

    # 5. Frame after cooldown elapsed (200ms) -> IDLE or new DWELL
    status, progress = dwell.update(GestureType.THUMBS_UP, pt, timestamp_ms=1700)
    assert status in (DwellStatus.IDLE, DwellStatus.DWELLING)


def test_dwell_accumulator_tremor_detection():
    dwell = DwellAccumulator(dwell_time_ms=600)

    # Feed high-frequency jitter coordinates
    for i in range(10):
        jitter_x = 0.5 + (0.1 if i % 2 == 0 else -0.1)
        pt = LandmarkPoint(jitter_x, 0.5, 0.0)
        dwell.update(GestureType.OPEN_PALM, pt, timestamp_ms=1000 + i * 50)

    assert dwell.is_tremor_detected is True
    # Smoothed pointer should be filtered towards center
    assert abs(dwell.smoothed_pointer.x - 0.5) < 0.1


# ===========================================================================
# 3. Spatial Target Detection & Hitbox Enlargement
# ===========================================================================

def test_spatial_target_detector():
    detector = SpatialTargetDetector()
    targets = [
        BoundingBox(0.1, 0.1, 0.3, 0.3, target_id="btn_cancel"),
        BoundingBox(0.6, 0.6, 0.9, 0.9, target_id="btn_confirm"),
    ]

    inside_pt = LandmarkPoint(0.2, 0.2, 0.0)
    outside_pt = LandmarkPoint(0.5, 0.5, 0.0)

    hit = detector.find_intersecting_target(inside_pt, targets)
    assert hit is not None
    assert hit.target_id == "btn_cancel"

    no_hit = detector.find_intersecting_target(outside_pt, targets)
    assert no_hit is None

    # Test hitbox enlargement factor (1.5x should capture outside_pt if close)
    near_pt = LandmarkPoint(0.35, 0.35, 0.0)
    enlarged_hit = detector.find_intersecting_target(near_pt, targets, enlargement_factor=1.5)
    assert enlarged_hit is not None
    assert enlarged_hit.target_id == "btn_cancel"


# ===========================================================================
# 4. Acoustic Voice Processing & Phonetic Matching
# ===========================================================================

def test_voice_preprocessor_and_soundex():
    text = "  Next Step, Please!  "
    norm = normalize_transcript(text)
    assert norm == "next step please"

    s1 = compute_soundex("confirm")
    s2 = compute_soundex("conform")
    assert s1 == s2  # Phonetically identical Soundex code


def test_voice_recognizer_exact_and_fuzzy():
    recognizer = VoiceRecognizer()

    # 1. Exact match
    res = recognizer.process_command(VoiceCommandPayload(transcript="next step"))
    assert res.action == "next_step"
    assert res.confidence >= 0.90

    # 2. Fuzzy match ("nxt stp")
    res_fuzzy = recognizer.process_command(VoiceCommandPayload(transcript="nxt stp"))
    assert res_fuzzy.action == "next_step"
    assert res_fuzzy.confidence >= 0.70

    # 3. Emergency stop safety critical check
    res_estop = recognizer.process_command(VoiceCommandPayload(transcript="emergency stop"))
    assert res_estop.action == "emergency_stop"
    assert res_estop.is_safety_critical is True


def test_acoustic_noise_filter():
    noise_filter = AcousticNoiseFilter(min_snr_db=10.0)

    clear_feat = AcousticFeatures(is_speech_present=True, estimated_snr_db=25.0)
    noisy_feat = AcousticFeatures(is_speech_present=True, estimated_snr_db=4.0)

    is_clear, score1 = noise_filter.evaluate_clarity(clear_feat)
    assert is_clear is True
    assert score1 >= 0.80

    is_clear_noisy, score2 = noise_filter.evaluate_clarity(noisy_feat)
    assert is_clear_noisy is False
    assert score2 < 0.50


# ===========================================================================
# 5. Multimodal Cross-Modal Temporal Fusion Tests
# ===========================================================================

def test_multimodal_reinforcing_fusion():
    engine = CrossModalFusionEngine()

    items = [
        MultimodalInputItem(
            mode=InputModality.GESTURE,
            raw_intent="thumbs_up",
            confidence=0.90,
            timestamp_ms=1000,
        ),
        MultimodalInputItem(
            mode=InputModality.VOICE,
            raw_intent="confirm",
            confidence=0.90,
            timestamp_ms=1100,
        ),
    ]

    res = engine.fuse(items)
    assert res.fused_action == "confirm_action"
    # Reinforcement: 1 - (1 - 0.9)*(1 - 0.9) = 0.99
    assert math.isclose(res.fused_confidence, 0.99, rel_tol=1e-2)
    assert res.fusion_strategy == FusionStrategy.REINFORCING
    assert res.requires_confirmation is False


def test_multimodal_spatial_complementary_fusion():
    engine = CrossModalFusionEngine()

    items = [
        MultimodalInputItem(
            mode=InputModality.GESTURE,
            raw_intent="pointing",
            confidence=0.85,
            timestamp_ms=1000,
            spatial_target="part_slot_4",
        ),
        MultimodalInputItem(
            mode=InputModality.VOICE,
            raw_intent="confirm",
            confidence=0.90,
            timestamp_ms=1050,
        ),
    ]

    res = engine.fuse(items)
    assert res.fused_action == "confirm_action"
    assert res.spatial_target_id == "part_slot_4"
    assert res.fusion_strategy == FusionStrategy.SPATIAL_COMPLEMENTARY


def test_multimodal_conflict_resolution():
    engine = CrossModalFusionEngine()

    # Conflicting gesture (thumbs_up -> confirm) vs voice (cancel)
    items = [
        MultimodalInputItem(
            mode=InputModality.GESTURE,
            raw_intent="thumbs_up",
            confidence=0.60,
            timestamp_ms=1000,
        ),
        MultimodalInputItem(
            mode=InputModality.VOICE,
            raw_intent="cancel",
            confidence=0.95,
            timestamp_ms=1050,
        ),
    ]

    res = engine.fuse(items)
    # High confidence voice should arbitrate and mandate confirmation
    assert res.fused_action == "cancel_action"
    assert res.fusion_strategy == FusionStrategy.CONFLICT_ARBITRATED
    assert res.requires_confirmation is True


# ===========================================================================
# 6. Safety Interlocks & AI Assistant Tests
# ===========================================================================

def test_safety_interlock_evaluator():
    evaluator = SafetyInterlockEvaluator()

    # 1. Normal safe action with high confidence
    ok, _ = evaluator.evaluate_execution_gating("next_step", confidence=0.85)
    assert ok is True

    # 2. Critical action without secondary confirmation -> GATED
    gated, msg = evaluator.evaluate_execution_gating("voltage_adjustment", confidence=0.95, is_secondary_confirmed=False)
    assert gated is False
    assert "mandates explicit secondary confirmation" in msg

    # 3. Critical action WITH secondary confirmation -> ALLOWED
    allowed, _ = evaluator.evaluate_execution_gating(
        "voltage_adjustment",
        confidence=0.95,
        is_secondary_confirmed=True,
        user_roles=["supervisor"],
    )
    assert allowed is True

    # 4. Emergency stop -> ALWAYS permissible
    estop_ok, _ = evaluator.evaluate_execution_gating("emergency_stop", confidence=0.50)
    assert estop_ok is True


def test_ai_assistant_guidance_and_synthesis():
    assistant = AIAssistant()

    # Guidance
    guidance = assistant.explain_task_step(
        step_title="Fasten Bracket",
        step_description="Align bracket with chassis and insert M4 screws.",
        accessibility_level="simplified",
    )
    assert "Fasten Bracket" in guidance["headline"]
    assert guidance["recommended_gesture"] == "thumbs_up"

    # Workflow Synthesis
    spec = "1. Inspect wire harness\n2. Connect battery terminal\n3. Fasten chassis"
    workflow = assistant.generate_workflow_proposal(spec)
    assert workflow["total_steps"] == 3
    assert workflow["steps"][0]["title"] == "Inspect wire harness"


# ===========================================================================
# 7. Evidence-Based Adaptation & Personalization Tests
# ===========================================================================

def test_adaptation_engine_rule_of_evidence():
    engine = AdaptationEngine()
    worker_id = "worker_test_1"

    # 1. Single outlier difficulty -> NO recommendation
    engine.record_interaction(worker_id, InteractionEventRecord(is_tremor=True))
    proposals_1 = engine.evaluate_adaptations(worker_id, current_dwell_ms=600)
    assert len(proposals_1) == 0

    # 2. Inject 3 tremor difficulties (Rule of Evidence threshold)
    engine.record_interaction(worker_id, InteractionEventRecord(is_tremor=True))
    engine.record_interaction(worker_id, InteractionEventRecord(is_tremor=True))

    proposals_2 = engine.evaluate_adaptations(worker_id, current_dwell_ms=600, current_hitbox_factor=1.0)
    assert len(proposals_2) >= 1
    assert proposals_2[0].recommendation_type == "dwell_and_hitbox"
    assert proposals_2[0].suggested_dwell_ms == 750  # 600 + 150ms
    assert proposals_2[0].suggested_hitbox_factor == 1.25  # 1.0 * 1.25


# ===========================================================================
# 8. Unified AIService & Pipeline End-to-End Test
# ===========================================================================

def test_ai_service_singleton_end_to_end():
    service = AIService.get_instance()

    # Optical Frame
    tu_pts = generate_synthetic_landmarks(GestureType.THUMBS_UP)
    g_res = service.recognize_gesture(
        landmarks=[p.to_dict() for p in tu_pts],
        handedness="Right",
        worker_id="test_worker_e2e",
    )
    assert g_res.gesture == GestureType.THUMBS_UP

    # Voice Transcript
    v_res = service.process_voice_transcript("confirm", worker_id="test_worker_e2e")
    assert v_res.action == "confirm_action"

    # Multimodal Fusion
    f_res = service.fuse_inputs([
        {"mode": "gesture", "raw_intent": "thumbs_up", "confidence": 0.92, "timestamp_ms": 1000},
        {"mode": "voice", "raw_intent": "confirm", "confidence": 0.94, "timestamp_ms": 1050},
    ])
    assert f_res.fused_action == "confirm_action"
    assert f_res.fused_confidence >= 0.98
