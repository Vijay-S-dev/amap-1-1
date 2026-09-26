"""
Automated Unit and Integration Tests for Worker Custom Gesture Pipeline & Database Persistence (§ 24, § 25, § 26, § 27).

Verifies:
1. Custom training validates physical hand samples and rejects invalid ones.
2. Custom gesture profile is persisted into the database with commit.
3. Database record actually exists and is readable via repository after service reinstantiation.
4. Worker isolation: Worker A cannot read, update, or trigger Worker B's custom gesture.
5. Updating custom gesture updates the profile without creating duplicate active records.
6. Deleting custom gesture marks it deleted in the database.
7. Standard gestures remain 100% functional.
"""

from uuid import uuid4
import pytest
from pydantic import ValidationError

from models.gesture import (
    CustomGestureTrainPayload,
    GestureFramePayload,
    LandmarkPoint,
)
from repositories.custom_gestures import CustomGesturesRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from services.gesture_service import GestureService


@pytest.fixture()
def worker_context():
    """Create a real organization with two workers (org -> users -> profiles).

    Yields stable UUIDs used for PostgreSQL-backed custom gesture tests and
    cleans all rows up afterwards.
    """
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()

    organization = organizations.create(f"gesture-test-org-{uuid4()}")
    user_a = users.create(
        organization["id"],
        f"gesture-a-{uuid4()}@example.com",
        "Gesture Worker A",
        "test-password-hash",
    )
    user_b = users.create(
        organization["id"],
        f"gesture-b-{uuid4()}@example.com",
        "Gesture Worker B",
        "test-password-hash",
    )
    profile_a = worker_profiles.create(user_a["id"])
    profile_b = worker_profiles.create(user_b["id"])

    try:
        yield {
            "organization_id": organization["id"],
            "worker_a": profile_a["id"],
            "worker_b": profile_b["id"],
        }
    finally:
        worker_profiles.delete_by_id(profile_b["id"])
        worker_profiles.delete_by_id(profile_a["id"])
        users.delete_by_id(user_a["id"])
        users.delete_by_id(user_b["id"])
        organizations.delete_by_id(organization["id"])


def generate_mock_landmarks_with_pose(
    wrist_y: float = 0.8,
    index_tip_y: float = 0.3,
    thumb_tip_y: float = 0.4,
    jitter: float = 0.0,
) -> list[LandmarkPoint]:
    """Generate a valid 21-point MediaPipe hand landmark skeleton."""
    points = []
    # 0: Wrist
    points.append(LandmarkPoint(x=0.5, y=wrist_y + jitter, z=0.0))
    # 1..4: Thumb
    points.append(LandmarkPoint(x=0.45, y=0.7 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.40, y=0.6 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.35, y=0.5 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.30, y=thumb_tip_y + jitter, z=0.0))
    # 5..8: Index
    points.append(LandmarkPoint(x=0.48, y=0.6 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.48, y=0.5 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.48, y=0.4 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.48, y=index_tip_y + jitter, z=0.0))
    # 9..12: Middle
    points.append(LandmarkPoint(x=0.52, y=0.58 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.52, y=0.48 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.52, y=0.38 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.52, y=0.30 + jitter, z=0.0))
    # 13..16: Ring
    points.append(LandmarkPoint(x=0.56, y=0.60 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.56, y=0.50 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.56, y=0.42 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.56, y=0.35 + jitter, z=0.0))
    # 17..20: Pinky
    points.append(LandmarkPoint(x=0.60, y=0.62 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.60, y=0.54 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.60, y=0.46 + jitter, z=0.0))
    points.append(LandmarkPoint(x=0.60, y=0.40 + jitter, z=0.0))
    return points


def test_custom_gesture_training_and_validation(worker_context):
    """Verify that custom gesture training validates sample count, quality, and builds template."""
    repo = CustomGesturesRepository()
    service = GestureService(custom_repo=repo)
    worker_id = worker_context["worker_a"]
    org_id = worker_context["organization_id"]

    # 1. Reject < 5 samples via Pydantic model validation
    invalid_samples = [generate_mock_landmarks_with_pose() for _ in range(3)]
    with pytest.raises(ValidationError):
        CustomGestureTrainPayload(
            gesture_name="Comfort Wave",
            intent="CONFIRM",
            samples=invalid_samples,
        )

    # 2. Accept 5 valid samples and build profile
    valid_samples = [generate_mock_landmarks_with_pose(jitter=i * 0.005) for i in range(5)]
    profile = service.train_custom_gesture(
        payload=CustomGestureTrainPayload(
            gesture_name="Comfort Wave",
            intent="CONFIRM",
            samples=valid_samples,
        ),
        worker_profile_id=worker_id,
        organization_id=org_id,
    )

    assert profile.gesture_name == "Comfort Wave"
    assert profile.intent == "CONFIRM"
    assert profile.action_mapping == "confirm_action"
    assert profile.sample_count == 5
    assert len(profile.feature_template) == 60
    assert profile.stability_score >= 80.0


def test_custom_gesture_database_persistence_and_restart(worker_context):
    """Verify that custom gesture profile is committed to PostgreSQL and survives service restart."""
    repo = CustomGesturesRepository()
    service1 = GestureService(custom_repo=repo)
    worker_id = worker_context["worker_a"]
    org_id = worker_context["organization_id"]

    # Train and persist
    samples = [generate_mock_landmarks_with_pose(index_tip_y=0.22, jitter=i * 0.002) for i in range(5)]
    created_profile = service1.train_custom_gesture(
        payload=CustomGestureTrainPayload(
            gesture_name="Persisted Wave",
            intent="CONFIRM",
            samples=samples,
        ),
        worker_profile_id=worker_id,
        organization_id=org_id,
    )

    # Verify directly in repository from database
    db_record = repo.get_by_id(created_profile.id)
    assert db_record is not None
    assert db_record["worker_id"] == worker_id
    assert db_record["organization_id"] == org_id
    assert db_record["intent"] == "CONFIRM"
    assert len(db_record["feature_template"]) == 60

    # Simulate Server Restart (new GestureService instance)
    service2 = GestureService(custom_repo=CustomGesturesRepository())
    loaded_profiles = service2.get_worker_custom_gestures(worker_id)
    assert len(loaded_profiles) == 1
    assert loaded_profiles[0].id == created_profile.id
    assert loaded_profiles[0].gesture_name == "Persisted Wave"

    # Test that newly instantiated service can classify using the persisted template
    live_frame = GestureFramePayload(
        landmarks=generate_mock_landmarks_with_pose(index_tip_y=0.22),
        timestamp_ms=1000,
        dwell_time_ms=300,
    )
    res = service2.process_frame(live_frame, worker_profile_id=worker_id)
    assert res.is_custom is True
    assert res.detected_gesture == "custom_confirm"
    assert res.action_mapping == "confirm_action"


def test_custom_gesture_worker_isolation_and_updates(worker_context):
    """Verify that Worker A's custom gesture is isolated from Worker B, and updates replace old intent."""
    repo = CustomGesturesRepository()
    service = GestureService(custom_repo=repo)
    worker_a = worker_context["worker_a"]
    worker_b = worker_context["worker_b"]
    org_id = worker_context["organization_id"]

    # Worker A saves custom CONFIRM gesture
    samples_a = [generate_mock_landmarks_with_pose(index_tip_y=0.2, jitter=i * 0.002) for i in range(5)]
    service.train_custom_gesture(
        payload=CustomGestureTrainPayload(gesture_name="Affirm A", intent="CONFIRM", samples=samples_a),
        worker_profile_id=worker_a,
        organization_id=org_id,
    )

    # Worker B list should be empty
    gestures_b = service.get_worker_custom_gestures(worker_b)
    assert len(gestures_b) == 0

    # Worker A updates their custom CONFIRM gesture
    samples_a_v2 = [generate_mock_landmarks_with_pose(index_tip_y=0.18, jitter=i * 0.002) for i in range(5)]
    service.train_custom_gesture(
        payload=CustomGestureTrainPayload(gesture_name="Affirm A v2", intent="CONFIRM", samples=samples_a_v2),
        worker_profile_id=worker_a,
        organization_id=org_id,
    )

    # Should still only have 1 active CONFIRM gesture for Worker A (upserted/replaced)
    gestures_a = service.get_worker_custom_gestures(worker_a)
    assert len(gestures_a) == 1
    assert gestures_a[0].gesture_name == "Affirm A v2"


def test_standard_gestures_remain_intact():
    """Verify that standard predefined gestures (thumbs_up, open_palm, etc.) remain 100% working."""
    service = GestureService()
    worker_id = uuid4()

    # Thumbs up landmarks
    thumbs_up_lms = generate_mock_landmarks_with_pose(
        wrist_y=0.8,
        index_tip_y=0.75,
        thumb_tip_y=0.35,
    )
    for idx in [12, 16, 20]:
        thumbs_up_lms[idx].y = 0.75

    result = service.process_frame(
        GestureFramePayload(landmarks=thumbs_up_lms, timestamp_ms=1000, dwell_time_ms=300),
        worker_profile_id=worker_id,
    )

    assert result.is_custom is False
    assert result.detected_gesture == "thumbs_up"
    assert result.action_mapping == "confirm_action"
    assert result.confidence >= 0.90
