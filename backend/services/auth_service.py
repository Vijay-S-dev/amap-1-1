"""
Authentication and identity verification service for AMAP.

Handles credential verification, role/permission resolution, JWT token issuance,
and token-to-user context resolution.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

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
from utils.security import create_access_token, decode_access_token, verify_password


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

        user_role_links = self.user_roles_repo.get_by_user_id(user_id)
        for link in user_role_links:
            role = self.roles_repo.get_by_id(link["role_id"])
            if role:
                role_names.append(role["name"])
                # Fetch permissions linked to this role
                role_perm_links = self.role_permissions_repo.get_by_role_id(role["id"])
                for rp in role_perm_links:
                    perm = self.permissions_repo.get_by_id(rp["permission_id"])
                    if perm and perm["name"] not in permission_names:
                        permission_names.append(perm["name"])

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
        user_data = self.users_repo.get_by_email(organization_id, email.lower().strip())
        if not user_data:
            raise UnauthorizedError("Invalid email or password.")

        if user_data.get("status") != "active":
            raise UnauthorizedError("User account is inactive or archived.")

        # Verify password hash
        if not verify_password(password, user_data.get("password_hash", "")):
            raise UnauthorizedError("Invalid email or password.")

        user_id = user_data["id"]
        roles, permissions = self._resolve_roles_and_permissions(user_id)

        worker_profile = self.worker_profiles_repo.get_by_user_id(user_id)
        worker_profile_id = str(worker_profile["id"]) if worker_profile else None

        # Build JWT claims payload
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
        Decode and verify an access token, ensuring the user is still active in the database.
        """
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise UnauthorizedError(f"Invalid authentication token: {exc}") from exc

        sub = payload.get("sub")
        org_id = payload.get("organization_id")
        if not sub or not org_id:
            raise UnauthorizedError("Token is missing required subject/organization claims.")

        user_data = self.users_repo.get_by_id(UUID(sub))
        if not user_data or user_data.get("status") != "active":
            raise UnauthorizedError("User no longer exists or is inactive.")

        worker_profile = self.worker_profiles_repo.get_by_user_id(user_data["id"])
        worker_profile_id = worker_profile["id"] if worker_profile else None

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
