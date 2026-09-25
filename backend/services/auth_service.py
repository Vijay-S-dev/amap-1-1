"""
Authentication and identity verification service for AMAP.

Handles credential verification, role/permission resolution, JWT token issuance,
and token-to-user context resolution. Supports resilient development fallbacks.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

from app.config import get_settings
from models.auth import AuthenticatedUserContext, TokenResponse
from models.user import UserInDB
from repositories.permissions import PermissionsRepository
from repositories.role_permissions import RolePermissionsRepository
from repositories.roles import RolesRepository
from repositories.user_roles import UserRolesRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from services.base import NotFoundError, UnauthorizedError
from utils.security import create_access_token, decode_access_token, hash_password, verify_password


# Demo in-memory fallback users for development and testing resilience
_DEV_DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "alex.worker@amap.com": {
        "id": UUID("c0000000-0000-0000-0000-000000000003"),
        "organization_id": UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65"),
        "email": "alex.worker@amap.com",
        "full_name": "Alex Morgan",
        "password_hash": "pbkdf2_sha256$600000$5a80572eefda2f48d91b8a531e289bf5$715dd2475e2a229c2d1b7470d0da0970a0dc3eb9ae05b1c55d07010f37d38ae8",  # SecurePassword123!
        "status": "active",
        "roles": ["worker"],
        "permissions": ["session:read", "session:write", "task:execute", "assistance:request"],
        "worker_profile_id": UUID("d0000000-0000-0000-0000-000000000001"),
    },
    "maria.newhire@amap.com": {
        "id": UUID("c0000000-0000-0000-0000-000000000004"),
        "organization_id": UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65"),
        "email": "maria.newhire@amap.com",
        "full_name": "Maria Rodriguez",
        "password_hash": "pbkdf2_sha256$600000$5a80572eefda2f48d91b8a531e289bf5$715dd2475e2a229c2d1b7470d0da0970a0dc3eb9ae05b1c55d07010f37d38ae8",  # SecurePassword123!
        "status": "active",
        "roles": ["worker"],
        "permissions": ["session:read", "session:write", "task:execute", "assistance:request"],
        "worker_profile_id": UUID("d0000000-0000-0000-0000-000000000002"),
    },
    "supervisor@amap.com": {
        "id": UUID("c0000000-0000-0000-0000-000000000002"),
        "organization_id": UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65"),
        "email": "supervisor@amap.com",
        "full_name": "Elena Rostova",
        "password_hash": "pbkdf2_sha256$600000$5a80572eefda2f48d91b8a531e289bf5$715dd2475e2a229c2d1b7470d0da0970a0dc3eb9ae05b1c55d07010f37d38ae8",  # SecurePassword123!
        "status": "active",
        "roles": ["supervisor"],
        "permissions": ["session:read", "session:write", "task:read", "assistance:manage", "worker:read"],
        "worker_profile_id": None,
    },
    "admin@amap.com": {
        "id": UUID("c0000000-0000-0000-0000-000000000001"),
        "organization_id": UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65"),
        "email": "admin@amap.com",
        "full_name": "Marcus Vance",
        "password_hash": "pbkdf2_sha256$600000$5a80572eefda2f48d91b8a531e289bf5$715dd2475e2a229c2d1b7470d0da0970a0dc3eb9ae05b1c55d07010f37d38ae8",  # SecurePassword123!
        "status": "active",
        "roles": ["organization_admin", "admin"],
        "permissions": ["admin:access", "organization:write", "user:write", "workflow:write", "audit:read"],
        "worker_profile_id": None,
    },
}


class AuthService:
    """Business logic for authentication and token validation."""

    def __init__(
        self,
        users_repo: Optional[UsersRepository] = None,
        user_roles_repo: Optional[UserRolesRepository] = None,
        roles_repo: Optional[RolesRepository] = None,
        role_permissions_repo: Optional[RolePermissionsRepository] = None,
        permissions_repo: Optional[PermissionsRepository] = None,
        worker_profiles_repo: Optional[WorkerProfilesRepository] = None,
    ) -> None:
        self.users_repo = users_repo or UsersRepository()
        self.user_roles_repo = user_roles_repo or UserRolesRepository()
        self.roles_repo = roles_repo or RolesRepository()
        self.role_permissions_repo = (
            role_permissions_repo or RolePermissionsRepository()
        )
        self.permissions_repo = permissions_repo or PermissionsRepository()
        self.worker_profiles_repo = (
            worker_profiles_repo or WorkerProfilesRepository()
        )

    def _resolve_roles_and_permissions(
        self,
        user_id: UUID,
    ) -> Tuple[List[str], List[str]]:
        """Resolve all role names and permission names assigned to a user."""
        role_names: List[str] = []
        permission_names: List[str] = []

        try:
            user_role_links = self.user_roles_repo.get_by_user_id(user_id)
            for link in user_role_links:
                role = self.roles_repo.get_by_id(link["role_id"])
                if role:
                    role_names.append(role["name"])
                    role_perm_links = self.role_permissions_repo.get_by_role_id(role["id"])
                    for rp in role_perm_links:
                        perm = self.permissions_repo.get_by_id(rp["permission_id"])
                        if perm and perm["name"] not in permission_names:
                            permission_names.append(perm["name"])
        except Exception:
            pass

        return role_names, permission_names

    def authenticate_user(
        self,
        organization_id: UUID,
        email: str,
        password: str,
    ) -> Tuple[UserInDB, TokenResponse]:
        """
        Authenticate a user by organization, email, and password.
        Returns the user record and a signed JWT access token.
        """
        clean_email = email.lower().strip()
        user_data = None

        settings = get_settings()

        # 1. Attempt database lookup
        try:
            user_data = self.users_repo.get_by_email(organization_id, clean_email)
        except Exception:
            user_data = None

        # 2. Resilient fallback for seeded demo accounts (DEVELOPMENT ONLY if explicitly enabled)
        is_demo_fallback = False
        if not user_data and not settings.is_production and settings.enable_dev_demo_users:
            if clean_email in _DEV_DEMO_USERS:
                demo = _DEV_DEMO_USERS[clean_email]
                user_data = {
                    "id": demo["id"],
                    "organization_id": demo["organization_id"],
                    "email": demo["email"],
                    "full_name": demo["full_name"],
                    "password_hash": demo["password_hash"],
                    "status": demo["status"],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                is_demo_fallback = True

        if not user_data:
            raise UnauthorizedError("Invalid email or password.")

        if user_data.get("status") != "active":
            raise UnauthorizedError("User account is inactive or archived.")

        # 3. Verify password hash using PBKDF2 (no plaintext bypass)
        stored_hash = user_data.get("password_hash", "")
        if not verify_password(password, stored_hash):
            raise UnauthorizedError("Invalid email or password.")

        user_id = user_data["id"]

        if is_demo_fallback:
            demo = _DEV_DEMO_USERS[clean_email]
            roles = demo["roles"]
            permissions = demo["permissions"]
            worker_profile_id = str(demo["worker_profile_id"]) if demo["worker_profile_id"] else None
        else:
            roles, permissions = self._resolve_roles_and_permissions(user_id)
            try:
                worker_profile = self.worker_profiles_repo.get_by_user_id(user_id)
                worker_profile_id = str(worker_profile["id"]) if worker_profile else None
            except Exception:
                worker_profile_id = None

        # 4. Build JWT claims payload
        token_payload = {
            "sub": str(user_id),
            "organization_id": str(organization_id),
            "email": user_data["email"],
            "roles": roles,
            "permissions": permissions,
            "worker_profile_id": worker_profile_id,
        }

        settings = get_settings()
        token = create_access_token(token_payload)

        return (
            UserInDB.model_validate(user_data),
            TokenResponse(
                access_token=token,
                token_type="bearer",
                expires_in=settings.access_token_expire_minutes * 60,
            ),
        )

    def verify_token(self, token: str) -> AuthenticatedUserContext:
        """
        Decode and verify an access token, ensuring the user is active.
        """
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise UnauthorizedError(f"Invalid authentication token: {exc}") from exc

        sub = payload.get("sub")
        org_id = payload.get("organization_id")
        email = payload.get("email", "")

        if not sub or not org_id:
            raise UnauthorizedError("Token is missing required subject/organization claims.")

        user_data = None
        try:
            user_data = self.users_repo.get_by_id(UUID(sub))
        except Exception:
            user_data = None

        if not user_data and not settings.is_production and settings.enable_dev_demo_users:
            if email in _DEV_DEMO_USERS:
                demo = _DEV_DEMO_USERS[email]
                user_data = {
                    "id": demo["id"],
                    "organization_id": demo["organization_id"],
                    "email": demo["email"],
                    "full_name": demo["full_name"],
                    "status": demo["status"],
                }

        if not user_data or user_data.get("status") != "active":
            raise UnauthorizedError("User no longer exists or is inactive.")

        worker_profile_id = None
        if payload.get("worker_profile_id"):
            try:
                worker_profile_id = UUID(payload["worker_profile_id"])
            except Exception:
                worker_profile_id = None

        return AuthenticatedUserContext(
            user_id=user_data["id"],
            organization_id=UUID(org_id),
            email=user_data["email"],
            full_name=user_data["full_name"],
            status=user_data["status"],
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            worker_profile_id=worker_profile_id,
        )
