from uuid import uuid4

from repositories.notifications import NotificationsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository


def create_dependencies():
    organizations_repository = OrganizationsRepository()
    users_repository = UsersRepository()

    suffix = str(uuid4())

    organization = organizations_repository.create(
        name=f"test-notification-org-{suffix}",
    )

    user = users_repository.create(
        organization["id"],
        f"notification-{suffix}@example.com",
        f"Notification User {suffix}",
        "test-password-hash",
    )

    return {
        "organization": organization,
        "user": user,
    }


def test_create_and_get_notification():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="test",
        title="Test notification",
        message="This is a test notification.",
        notification_data={"source": "test"},
    )

    fetched_notification = repository.get_by_id(notification["id"])

    assert fetched_notification is not None
    assert fetched_notification["id"] == notification["id"]
    assert (
        fetched_notification["organization_id"]
        == dependencies["organization"]["id"]
    )
    assert (
        fetched_notification["recipient_user_id"]
        == dependencies["user"]["id"]
    )
    assert fetched_notification["notification_type"] == "test"
    assert fetched_notification["title"] == "Test notification"
    assert fetched_notification["message"] == "This is a test notification."
    assert fetched_notification["notification_data"] == {"source": "test"}
    assert fetched_notification["status"] == "unread"
    assert fetched_notification["read_at"] is None


def test_list_by_organization_id_contains_created_notification():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="organization_test",
        title="Organization notification",
        message="Test organization notification.",
    )

    notifications = repository.list_by_organization_id(
        dependencies["organization"]["id"]
    )

    notification_ids = [item["id"] for item in notifications]

    assert notification["id"] in notification_ids


def test_list_by_recipient_user_id_contains_created_notification():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="recipient_test",
        title="Recipient notification",
        message="Test recipient notification.",
    )

    notifications = repository.list_by_recipient_user_id(
        dependencies["user"]["id"]
    )

    notification_ids = [item["id"] for item in notifications]

    assert notification["id"] in notification_ids


def test_list_by_status_contains_created_notification():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="status_test",
        title="Status notification",
        message="Test status notification.",
        status="unread",
    )

    notifications = repository.list_by_status("unread")

    notification_ids = [item["id"] for item in notifications]

    assert notification["id"] in notification_ids


def test_update_status():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="update_test",
        title="Update notification",
        message="Test update notification.",
    )

    updated_notification = repository.update_status(
        notification["id"],
        "archived",
    )

    assert updated_notification is not None
    assert updated_notification["id"] == notification["id"]
    assert updated_notification["status"] == "archived"

    fetched_notification = repository.get_by_id(notification["id"])

    assert fetched_notification is not None
    assert fetched_notification["status"] == "archived"


def test_mark_as_read():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="read_test",
        title="Read notification",
        message="Test read notification.",
    )

    updated_notification = repository.mark_as_read(notification["id"])

    assert updated_notification is not None
    assert updated_notification["id"] == notification["id"]
    assert updated_notification["status"] == "read"
    assert updated_notification["read_at"] is not None

    fetched_notification = repository.get_by_id(notification["id"])

    assert fetched_notification is not None
    assert fetched_notification["status"] == "read"
    assert fetched_notification["read_at"] is not None


def test_delete_by_id_returns_true_for_existing_notification():
    dependencies = create_dependencies()
    repository = NotificationsRepository()

    notification = repository.create(
        organization_id=dependencies["organization"]["id"],
        recipient_user_id=dependencies["user"]["id"],
        notification_type="delete_test",
        title="Delete notification",
        message="Test delete notification.",
    )

    deleted = repository.delete_by_id(notification["id"])

    assert deleted is True
    assert repository.get_by_id(notification["id"]) is None


def test_delete_by_id_returns_false_for_missing_notification():
    repository = NotificationsRepository()

    deleted = repository.delete_by_id(uuid4())

    assert deleted is False
