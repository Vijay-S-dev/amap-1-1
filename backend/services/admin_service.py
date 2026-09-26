"""
Admin and system configuration service for AMAP.

Provides administrative business logic for:
- Managing tenant-level and station interaction presets.
- Organization settings and status management.
- User status updates, role assignments, and permission audits.
- Organization-scoped audit log querying.
- Automatic audit log emission for all administrative modifications.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from models.audit import AuditEventRead
from models.interaction import (
    InteractionConfigurationCreate,
    InteractionConfigurationRead,
    InteractionConfigurationUpdate,
)
from models.organization import OrganizationRead, OrganizationUpdate
from models.user import UserRead
from psycopg import errors

from repositories.audit_events import AuditEventsRepository
from repositories.interaction_configurations import InteractionConfigurationsRepository
from repositories.organizations import OrganizationsRepository
from repositories.roles import RolesRepository
from repositories.user_roles import UserRolesRepository
from repositories.users import UsersRepository
from services.base import ConflictError, NotFoundError, ValidationError


class AdminService:
    """Business logic for system administration, configurations, and tenant audits."""

    def __init__(
        self,
        configs_repo: Optional[InteractionConfigurationsRepository] = None,
        orgs_repo: Optional[OrganizationsRepository] = None,
        users_repo: Optional[UsersRepository] = None,
        roles_repo: Optional[RolesRepository] = None,
        user_roles_repo: Optional[UserRolesRepository] = None,
        audit_repo: Optional[AuditEventsRepository] = None,
    ) -> None:
        self.configs_repo = configs_repo or InteractionConfigurationsRepository()
        self.orgs_repo = orgs_repo or OrganizationsRepository()
        self.users_repo = users_repo or UsersRepository()
        self.roles_repo = roles_repo or RolesRepository()
        self.user_roles_repo = user_roles_repo or UserRolesRepository()
        self.audit_repo = audit_repo or AuditEventsRepository()

    # -------------------------------------------------------------------------
    # Interaction Configurations
    # -------------------------------------------------------------------------

    def list_configs(self, organization_id: UUID) -> List[InteractionConfigurationRead]:
        """List all interaction configurations for an organization."""
        records = self.configs_repo.list_by_organization_id(organization_id)
        return [
            InteractionConfigurationRead(
                id=r["id"],
                organization_id=r["organization_id"],
                name=r["name"],
                description=r.get("description"),
                config_data=r.get("config_data") or {},
                status=r.get("status", "active"),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in records
        ]

    def get_config(
        self,
        config_id: UUID,
        organization_id: UUID,
    ) -> InteractionConfigurationRead:
        """Get an interaction configuration by ID enforcing tenant boundary."""
        rec = self.configs_repo.get_by_id(config_id)
        if not rec or rec["organization_id"] != organization_id:
            raise NotFoundError("Interaction configuration not found in your organization.")

        return InteractionConfigurationRead(
            id=rec["id"],
            organization_id=rec["organization_id"],
            name=rec["name"],
            description=rec.get("description"),
            config_data=rec.get("config_data") or {},
            status=rec.get("status", "active"),
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
        )

    def create_config(
        self,
        organization_id: UUID,
        payload: InteractionConfigurationCreate,
        actor_id: UUID,
    ) -> InteractionConfigurationRead:
        """Create a new interaction preset and emit audit log."""
        created = self.configs_repo.create(
            organization_id=organization_id,
            name=payload.name,
            description=payload.description,
            status=payload.status.value if hasattr(payload.status, "value") else str(payload.status),
            config_data=payload.config_data or {},
        )

        # Emit audit record
        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="interaction_config.created",
            resource_type="interaction_configuration",
            resource_id=created["id"],
            event_data={"name": payload.name, "description": payload.description},
        )

        return InteractionConfigurationRead(
            id=created["id"],
            organization_id=created["organization_id"],
            name=created["name"],
            description=created.get("description"),
            config_data=created.get("config_data") or {},
            status=created.get("status", "active"),
            created_at=created["created_at"],
            updated_at=created["updated_at"],
        )

    def update_config(
        self,
        config_id: UUID,
        organization_id: UUID,
        payload: InteractionConfigurationUpdate,
        actor_id: UUID,
    ) -> InteractionConfigurationRead:
        """Update an interaction configuration and emit audit log."""
        existing = self.configs_repo.get_by_id(config_id)
        if not existing or existing["organization_id"] != organization_id:
            raise NotFoundError("Interaction configuration not found.")

        new_name = payload.name or existing["name"]
        new_desc = payload.description if payload.description is not None else existing.get("description")
        new_status = (
            payload.status.value if hasattr(payload.status, "value") else str(payload.status)
        ) if payload.status is not None else existing.get("status", "active")

        new_config_data = (
            payload.config_data if payload.config_data is not None
            else existing.get("config_data") or {}
        )

        updated = self.configs_repo.update(
            interaction_configuration_id=config_id,
            name=new_name,
            description=new_desc,
            status=new_status,
            config_data=new_config_data,
        )

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="interaction_config.updated",
            resource_type="interaction_configuration",
            resource_id=config_id,
            event_data={"name": new_name, "status": new_status, "config_data": new_config_data},
        )

        return InteractionConfigurationRead(
            id=updated["id"],
            organization_id=updated["organization_id"],
            name=updated["name"],
            description=updated.get("description"),
            config_data=updated.get("config_data") or {},
            status=updated.get("status", "active"),
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
        )

    def delete_config(
        self,
        config_id: UUID,
        organization_id: UUID,
        actor_id: UUID,
    ) -> bool:
        """Delete an interaction configuration and emit audit log."""
        existing = self.configs_repo.get_by_id(config_id)
        if not existing or existing["organization_id"] != organization_id:
            raise NotFoundError("Interaction configuration not found.")

        deleted = self.configs_repo.delete_by_id(config_id)
        if deleted:
            self.audit_repo.create(
                organization_id=organization_id,
                actor_user_id=actor_id,
                event_type="interaction_config.deleted",
                resource_type="interaction_configuration",
                resource_id=config_id,
                event_data={"name": existing["name"]},
            )
        return deleted

    # -------------------------------------------------------------------------
    # Organization Management
    # -------------------------------------------------------------------------

    def get_organization(self, organization_id: UUID) -> OrganizationRead:
        """Retrieve current organization details."""
        org = self.orgs_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization not found.")
        return OrganizationRead.model_validate(org)

    def update_organization(
        self,
        organization_id: UUID,
        payload: OrganizationUpdate,
        actor_id: UUID,
    ) -> OrganizationRead:
        """Update organization details and emit audit log."""
        existing = self.orgs_repo.get_by_id(organization_id)
        if not existing:
            raise NotFoundError("Organization not found.")

        new_name = payload.name or existing["name"]
        new_status = (
            payload.status.value if hasattr(payload.status, "value") else str(payload.status)
        ) if payload.status is not None else existing["status"]

        if new_name != existing["name"]:
            clash = self.orgs_repo.get_by_name(new_name)
            if clash and clash["id"] != organization_id:
                raise ConflictError(f"An organization named '{new_name}' already exists.")

        try:
            updated = self.orgs_repo.update(
                organization_id=organization_id,
                name=new_name,
                status=new_status,
            )
        except errors.UniqueViolation:
            raise ConflictError(f"An organization named '{new_name}' already exists.")
        if not updated:
            raise NotFoundError("Organization not found.")

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="organization.updated",
            resource_type="organization",
            resource_id=organization_id,
            event_data={"name": new_name, "status": new_status},
        )

        return OrganizationRead.model_validate(updated)

    # -------------------------------------------------------------------------
    # User & Role Management
    # -------------------------------------------------------------------------

    def list_organization_users(self, organization_id: UUID) -> List[UserRead]:
        """List all users within the organization."""
        users = self.users_repo.list_by_organization(organization_id)
        return [UserRead.model_validate(u) for u in users]

    def update_user_status(
        self,
        user_id: UUID,
        organization_id: UUID,
        new_status: str,
        actor_id: UUID,
        reason: Optional[str] = None,
    ) -> UserRead:
        """Update user account status (e.g. suspend or activate)."""
        user = self.users_repo.get_by_id(user_id)
        if not user or user["organization_id"] != organization_id:
            raise NotFoundError("User not found in this organization.")

        updated = self.users_repo.update_status(user_id=user_id, status=new_status)
        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="user.status_updated",
            resource_type="user",
            resource_id=user_id,
            event_data={"previous_status": user["status"], "new_status": new_status, "reason": reason},
        )
        return UserRead.model_validate(updated)

    def assign_role(
        self,
        user_id: UUID,
        role_name: str,
        organization_id: UUID,
        actor_id: UUID,
    ) -> Dict[str, Any]:
        """Assign a role to a user and emit audit log."""
        user = self.users_repo.get_by_id(user_id)
        if not user or user["organization_id"] != organization_id:
            raise NotFoundError("User not found in this organization.")

        role = self.roles_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"Role '{role_name}' does not exist.")

        existing_assignment = self.user_roles_repo.get(user_id=user_id, role_id=role["id"])
        if not existing_assignment:
            assignment = self.user_roles_repo.create(user_id=user_id, role_id=role["id"])
            self.audit_repo.create(
                organization_id=organization_id,
                actor_user_id=actor_id,
                event_type="user.role_assigned",
                resource_type="user_role",
                resource_id=user_id,
                event_data={"role_name": role_name, "role_id": str(role["id"])},
            )
            return assignment
        return existing_assignment

    def revoke_role(
        self,
        user_id: UUID,
        role_name: str,
        organization_id: UUID,
        actor_id: UUID,
    ) -> bool:
        """Revoke a role from a user and emit audit log."""
        user = self.users_repo.get_by_id(user_id)
        if not user or user["organization_id"] != organization_id:
            raise NotFoundError("User not found in this organization.")

        role = self.roles_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"Role '{role_name}' does not exist.")

        deleted = self.user_roles_repo.delete(user_id=user_id, role_id=role["id"])
        if deleted:
            self.audit_repo.create(
                organization_id=organization_id,
                actor_user_id=actor_id,
                event_type="user.role_revoked",
                resource_type="user_role",
                resource_id=user_id,
                event_data={"role_name": role_name, "role_id": str(role["id"])},
            )
        return deleted

    # -------------------------------------------------------------------------
    # Audit Logs
    # -------------------------------------------------------------------------

    def query_audit_logs(
        self,
        organization_id: UUID,
        event_type: Optional[str] = None,
        actor_user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditEventRead]:
        """Query and filter organization audit trails."""
        records = self.audit_repo.list_by_organization_id(organization_id)
        filtered = records

        if event_type:
            filtered = [r for r in filtered if r.get("event_type") == event_type]
        if actor_user_id:
            filtered = [r for r in filtered if r.get("actor_user_id") == actor_user_id]
        if resource_type:
            filtered = [r for r in filtered if r.get("resource_type") == resource_type]
        filtered = filtered[: max(1, limit)]

        return [
            AuditEventRead(
                id=r["id"],
                organization_id=r["organization_id"],
                actor_user_id=r.get("actor_user_id"),
                event_type=r["event_type"],
                resource_type=r.get("resource_type"),
                resource_id=r.get("resource_id"),
                event_data=r.get("event_data") or {},
                occurred_at=r["occurred_at"],
                created_at=r["created_at"],
            )
            for r in filtered[:limit]
        ]
