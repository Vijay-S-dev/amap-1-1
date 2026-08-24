"""
Tests for AMAP Authentication Foundation (Phase 5).
Covers password hashing, JWT operations, AuthService business logic, and API endpoints.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from models.auth import LoginRequest
from services.auth_service import AuthService
from services.base import UnauthorizedError
from utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# =====================================================================
# Security Utilities Tests
# =====================================================================

def test_password_hashing_and_verification():
    raw = "SecurePassword123!"
    hashed = hash_password(raw)
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_lifecycle():
    payload = {"sub": str(uuid.uuid4()), "role": "admin"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)

    assert decoded["sub"] == payload["sub"]
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_token_expired():
    payload = {"sub": str(uuid.uuid4())}
    # Expired token in the past
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))
    with pytest.raises(ValueError, match="Token has expired."):
        decode_access_token(token)


def test_jwt_token_tampered():
    payload = {"sub": str(uuid.uuid4())}
    token = create_access_token(payload)
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tampered_signature"
    with pytest.raises(ValueError, match="Invalid token signature."):
        decode_access_token(tampered)


# =====================================================================
# AuthService Tests
# =====================================================================

def test_auth_service_authenticate_user_success():
    mock_users_repo = MagicMock()
    mock_user_roles_repo = MagicMock()
    mock_roles_repo = MagicMock()
    mock_role_perms_repo = MagicMock()
    mock_perms_repo = MagicMock()
    mock_worker_profiles_repo = MagicMock()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    perm_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    raw_pw = "Password123!"
    pw_hash = hash_password(raw_pw)

    mock_users_repo.get_by_email.return_value = {
        "id": user_id,
        "organization_id": org_id,
        "email": "worker@amap.org",
        "full_name": "Test Worker",
        "password_hash": pw_hash,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    mock_user_roles_repo.get_by_user_id.return_value = [
        {"user_id": user_id, "role_id": role_id}
    ]
    mock_roles_repo.get_by_id.return_value = {
        "id": role_id,
        "name": "worker",
    }
    mock_role_perms_repo.get_by_role_id.return_value = [
        {"role_id": role_id, "permission_id": perm_id}
    ]
    mock_perms_repo.get_by_id.return_value = {
        "id": perm_id,
        "name": "tasks:read",
    }
    mock_worker_profiles_repo.get_by_user_id.return_value = {
        "id": worker_id,
        "user_id": user_id,
    }

    service = AuthService(
        users_repo=mock_users_repo,
        user_roles_repo=mock_user_roles_repo,
        roles_repo=mock_roles_repo,
        role_permissions_repo=mock_role_perms_repo,
        permissions_repo=mock_perms_repo,
        worker_profiles_repo=mock_worker_profiles_repo,
    )

    user, token_resp = service.authenticate_user(
        organization_id=org_id,
        email="worker@amap.org",
        password=raw_pw,
    )

    assert user.id == user_id
    assert token_resp.token_type == "bearer"
    assert token_resp.access_token is not None

    # Verify decoded token contents
    decoded = decode_access_token(token_resp.access_token)
    assert decoded["sub"] == str(user_id)
    assert decoded["organization_id"] == str(org_id)
    assert decoded["roles"] == ["worker"]
    assert decoded["permissions"] == ["tasks:read"]
    assert decoded["worker_profile_id"] == str(worker_id)


def test_auth_service_authenticate_user_invalid_password():
    mock_users_repo = MagicMock()
    org_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_users_repo.get_by_email.return_value = {
        "id": uuid.uuid4(),
        "organization_id": org_id,
        "email": "worker@amap.org",
        "full_name": "Test Worker",
        "password_hash": hash_password("CorrectPassword123!"),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    service = AuthService(users_repo=mock_users_repo)
    with pytest.raises(UnauthorizedError, match="Invalid email or password."):
        service.authenticate_user(org_id, "worker@amap.org", "WrongPassword!")


def test_auth_service_authenticate_user_inactive():
    mock_users_repo = MagicMock()
    org_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_users_repo.get_by_email.return_value = {
        "id": uuid.uuid4(),
        "organization_id": org_id,
        "email": "worker@amap.org",
        "full_name": "Test Worker",
        "password_hash": hash_password("Password123!"),
        "status": "archived",
        "created_at": now,
        "updated_at": now,
    }

    service = AuthService(users_repo=mock_users_repo)
    with pytest.raises(UnauthorizedError, match="User account is inactive"):
        service.authenticate_user(org_id, "worker@amap.org", "Password123!")


# =====================================================================
# API Endpoints Tests
# =====================================================================

def test_api_login_and_me_flow():
    client = TestClient(app)

    # Directly mock AuthService dependencies via FastAPI dependency override
    from app.dependencies import get_auth_service

    mock_auth_service = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_auth_service.authenticate_user.return_value = (
        None,
        {
            "access_token": create_access_token(
                {"sub": str(user_id), "organization_id": str(org_id), "roles": ["worker"]}
            ),
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    try:
        # 1. Login success
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": str(org_id),
                "email": "user@example.com",
                "password": "Password123!",
            },
        )
        assert resp.status_code == 200
        token_data = resp.json()
        assert "access_token" in token_data

        token = token_data["access_token"]

        # 2. Access /me with Bearer token
        mock_auth_service.verify_token.return_value = {
            "user_id": str(user_id),
            "organization_id": str(org_id),
            "email": "user@example.com",
            "full_name": "Test Worker",
            "status": "active",
            "roles": ["worker"],
            "permissions": ["tasks:read"],
            "worker_profile_id": None,
        }

        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "user@example.com"
        assert me_resp.json()["roles"] == ["worker"]

    finally:
        app.dependency_overrides.clear()
