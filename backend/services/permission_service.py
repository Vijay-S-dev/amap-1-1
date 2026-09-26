"""
Organization-scoped permission matrix service.

Reads the permissions catalog and role_permissions grants for one organization,
and applies grant/revoke mutations with validation, invariant protection, and
audit logging. Every operation is tenant-isolated.
"""

from typing import Dict, List
from uuid import UUID

from models.permissions import (
    PermissionMatrixEntry,
    PermissionMatrixResponse,
    PermissionRead,
)
from repositories.audit_events import AuditEventsRepository
from repositories.permissions import PermissionsRepository
from repositories.role_permissions import RolePermissionsRepository
from repositories.roles import RolesRepository
from services.base import ConflictError, NotFoundError

# Roles rendered/managed in the governance matrix.
MATRIX_ROLES = ("admin", "organization_admin", "supervisor", "worker")

# Governance invariant: the admin role can never lose its configuration
# permission (prevents a lockout of the only role that can repair the matrix).
INVARIANT_GRANTS = (("admin", "admin:config"),)


class PermissionService:
    """Business logic for the organization permission matrix."""

    def __init__(
        self,
        permissions_repo: PermissionsRepository | None = None,
        role_permissions_repo: RolePermissionsRepository | None = None,
        roles_repo: RolesRepository | None = None,
        audit_repo: AuditEventsRepository | None = None,
    ) -> None:
        self.permissions_repo = permissions_repo or PermissionsRepository()
        self.role_permissions_repo = role_permissions_repo or RolePermissionsRepository()
        self.roles_repo = roles_repo or RolesRepository()
        self.audit_repo = audit_repo or AuditEventsRepository()

    def get_matrix(self, organization_id: UUID) -> PermissionMatrixResponse:
        """Return the full permission catalog with this organization's grants."""
        catalog = self.permissions_repo.list_all()
        grants = self.role_permissions_repo.list_matrix(organization_id)

        granted: Dict[str, set] = {role: set() for role in MATRIX_ROLES}
        for row in grants:
            role_name = row["role_name"]
            if role_name in granted:
                granted[role_name].add(row["permission_name"])

        entries: List[PermissionMatrixEntry] = []
        for perm in catalog:
            entries.append(
                PermissionMatrixEntry(
                    permission=PermissionRead.model_validate(perm),
                    roles={role: perm["name"] in granted[role] for role in MATRIX_ROLES},
                )
            )

        return PermissionMatrixResponse(
            organization_id=organization_id,
            roles=list(MATRIX_ROLES),
            permissions=entries,
        )

    def set_grant(
        self,
        organization_id: UUID,
        role_name: str,
        permission_name: str,
        granted: bool,
        actor_id: UUID,
    ) -> PermissionMatrixResponse:
        """Grant or revoke one permission for one role within an organization."""
        role = self.roles_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"Role '{role_name}' does not exist.")

        permission = self.permissions_repo.get_by_name(permission_name)
        if not permission:
            raise NotFoundError(f"Permission '{permission_name}' does not exist.")

        if role_name not in MATRIX_ROLES:
            raise NotFoundError(
                f"Role '{role_name}' is not part of the governance matrix."
            )

        if not granted and (role_name, permission_name) in INVARIANT_GRANTS:
            raise ConflictError(
                f"Permission '{permission_name}' cannot be revoked from role "
                "'admin' (governance invariant)."
            )

        existing = self.role_permissions_repo.get(
            organization_id, role["id"], permission["id"]
        )

        if granted and existing:
            raise ConflictError(
                f"Permission '{permission_name}' is already granted to '{role_name}'."
            )
        if not granted and not existing:
            raise ConflictError(
                f"Permission '{permission_name}' is not granted to '{role_name}'."
            )

        if granted:
            self.role_permissions_repo.create(
                organization_id, role["id"], permission["id"]
            )
            event_type = "permission.granted"
        else:
            self.role_permissions_repo.delete(
                organization_id, role["id"], permission["id"]
            )
            event_type = "permission.revoked"

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type=event_type,
            resource_type="permission",
            resource_id=permission["id"],
            event_data={"role": role_name, "permission": permission_name},
        )

        return self.get_matrix(organization_id)
