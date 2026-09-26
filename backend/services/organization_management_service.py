"""
Enterprise Organization Management Business Service for AMAP (§ 1-38).

Encapsulates all multi-tenant organization administration, department hierarchy,
supervisor/worker rosters and invitations, workflow definitions, aggregate operational
status, emergency oversight, and immutable audit logging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from models.enterprise_organization import (
    DepartmentCreatePayload,
    DepartmentItem,
    DepartmentUpdatePayload,
    EnterpriseWorkerItem,
    OrganizationAnalyticsSummary,
    OrganizationAuditEventItem,
    OrganizationDashboardKPIs,
    OrganizationProfileRead,
    OrganizationProfileUpdate,
    SupervisorInvitePayload,
    SupervisorItem,
    SupervisorUpdatePayload,
    WorkerInvitePayload,
    WorkflowCreatePayload,
    WorkflowStepItem,
    WorkflowTemplate,
    WorkflowUpdatePayload,
)
import secrets

from psycopg import errors

from repositories.assistance_requests import AssistanceRequestsRepository
from repositories.audit_events import AuditEventsRepository
from repositories.departments import DepartmentsRepository
from repositories.organizations import OrganizationsRepository
from repositories.tasks import TasksRepository
from repositories.worker_task_assignments import WorkerTaskAssignmentsRepository
from repositories.roles import RolesRepository
from repositories.user_departments import UserDepartmentsRepository
from repositories.user_roles import UserRolesRepository
from repositories.users import UsersRepository
from repositories.worker_readiness import WorkerReadinessRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.workflows import WorkflowsRepository
from repositories.workflow_steps import WorkflowStepsRepository
from services.base import ConflictError, NotFoundError, ValidationError
from utils.security import hash_password


class OrganizationManagementService:
    """Enterprise multi-tenant operations and governance management."""

    def __init__(
        self,
        orgs_repo: Optional[OrganizationsRepository] = None,
        depts_repo: Optional[DepartmentsRepository] = None,
        users_repo: Optional[UsersRepository] = None,
        workers_repo: Optional[WorkerProfilesRepository] = None,
        workflows_repo: Optional[WorkflowsRepository] = None,
        workflow_steps_repo: Optional[WorkflowStepsRepository] = None,
        tasks_repo: Optional[TasksRepository] = None,
        worker_task_assignments_repo: Optional[WorkerTaskAssignmentsRepository] = None,
        audit_repo: Optional[AuditEventsRepository] = None,
        assistance_repo: Optional[AssistanceRequestsRepository] = None,
        user_departments_repo: Optional[UserDepartmentsRepository] = None,
        roles_repo: Optional[RolesRepository] = None,
        user_roles_repo: Optional[UserRolesRepository] = None,
        worker_readiness_repo: Optional[WorkerReadinessRepository] = None,
    ) -> None:
        self.orgs_repo = orgs_repo or OrganizationsRepository()
        self.depts_repo = depts_repo or DepartmentsRepository()
        self.users_repo = users_repo or UsersRepository()
        self.workers_repo = workers_repo or WorkerProfilesRepository()
        self.workflows_repo = workflows_repo or WorkflowsRepository()
        self.workflow_steps_repo = workflow_steps_repo or WorkflowStepsRepository()
        self.tasks_repo = tasks_repo or TasksRepository()
        self.worker_task_assignments_repo = worker_task_assignments_repo or WorkerTaskAssignmentsRepository()
        self.audit_repo = audit_repo or AuditEventsRepository()
        self.assistance_repo = assistance_repo or AssistanceRequestsRepository()
        self.user_departments_repo = user_departments_repo or UserDepartmentsRepository()
        self.roles_repo = roles_repo or RolesRepository()
        self.user_roles_repo = user_roles_repo or UserRolesRepository()
        self.worker_readiness_repo = worker_readiness_repo or WorkerReadinessRepository()

    # =========================================================================
    # 1. Organization Dashboard KPIs (§ 5, § 34)
    # =========================================================================

    def get_organization_dashboard(self, organization_id: UUID) -> OrganizationDashboardKPIs:
        """Aggregate real database statistics for the organization operational dashboard.

        Worker KPIs come from the enterprise directory lifecycle, task KPIs
        from worker_task_assignments rows, and assistance/emergency counts
        from assistance_requests - no derived-from-invented-vocabulary
        constants.
        """
        org = self.orgs_repo.get_by_id(organization_id)
        org_name = org.get("name") if isinstance(org, dict) else None
        if not isinstance(org_name, str) or not org_name:
            org_name = "Unknown organization"

        workers = self.list_workers(organization_id, page=1, page_size=500)["items"]
        supervisors = self.list_supervisors(organization_id)
        departments = self.list_departments(organization_id)
        workflows = self.list_workflows(organization_id)

        total_workers = len(workers)
        active_workers = sum(1 for w in workers if w.status != "DEACTIVATED")
        available_workers = sum(1 for w in workers if w.status == "READY")
        working_workers = sum(1 for w in workers if w.status == "WORKING")

        completed_tasks = 0
        in_progress_tasks = 0
        pending_tasks = 0
        for task in self.tasks_repo.list_by_organization_id(organization_id):
            for assignment in self.worker_task_assignments_repo.list_by_task_id(task["id"]):
                st = assignment.get("status")
                if st == "completed":
                    completed_tasks += 1
                elif st == "in_progress":
                    in_progress_tasks += 1
                elif st == "assigned":
                    pending_tasks += 1

        assistance_tickets = self.get_assistance_overview(organization_id)
        emergency_events = self.get_emergency_events(organization_id)

        open_assistance = sum(
            1 for a in assistance_tickets
            if a.get("status") in ("open", "acknowledged", "in_progress")
        )
        utilization = (
            round((working_workers / total_workers) * 100.0, 1)
            if total_workers > 0 else 0.0
        )

        return OrganizationDashboardKPIs(
            organization_id=organization_id,
            organization_name=org_name,
            total_workers_count=total_workers,
            active_workers_count=active_workers,
            available_workers_count=available_workers,
            supervisors_count=len(supervisors),
            departments_count=len(departments),
            active_tasks_count=in_progress_tasks,
            completed_tasks_count=completed_tasks,
            pending_tasks_count=pending_tasks,
            open_assistance_requests_count=open_assistance,
            emergency_events_count=len(emergency_events),
            current_line_utilization_percent=utilization,
        )

    # 2. Organization Profile & Settings (§ 6, § 28)
    # =========================================================================

    def get_organization_profile(self, organization_id: UUID) -> OrganizationProfileRead:
        """Retrieve tenant profile and accessibility configurations from PostgreSQL."""
        org = self.orgs_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization not found.")

        now = datetime.now(timezone.utc)
        supported = org.get("supported_languages")
        accessibility = org.get("accessibility_defaults")
        return OrganizationProfileRead(
            id=org["id"],
            name=org["name"],
            organization_type=org.get("organization_type") or "industrial_manufacturing",
            industry=org.get("industry") or "Automotive & Aerospace Assembly",
            location=org.get("location") or "Main Operations Facility",
            contact_email=org.get("contact_email"),
            status=org.get("status", "active"),
            default_language=org.get("default_language") or "en",
            supported_languages=list(supported) if isinstance(supported, list) else ["en", "es", "ta", "hi", "de"],
            accessibility_defaults=dict(accessibility) if isinstance(accessibility, dict) else {
                "default_dwell_time_ms": 500,
                "high_contrast_default": False,
                "min_target_size_px": 48,
                "voice_confirmation_default": False,
            },
            created_at=org.get("created_at") or now,
            updated_at=org.get("updated_at") or now,
        )

    def update_organization_profile(
        self,
        organization_id: UUID,
        payload: OrganizationProfileUpdate,
        actor_id: UUID,
    ) -> OrganizationProfileRead:
        """Persist every exposed profile/settings field (was audit-only for
        everything except name, with the name update itself swallowed)."""
        org = self.orgs_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization not found.")

        changes = payload.model_dump(exclude_unset=True)
        name = changes.get("name", org["name"])

        if "supported_languages" in changes:
            langs = changes["supported_languages"]
            if not isinstance(langs, list) or not langs or not all(
                isinstance(x, str) and x for x in langs
            ):
                raise ValidationError("supported_languages must be a non-empty list of language codes.")
        if "accessibility_defaults" in changes and not isinstance(changes["accessibility_defaults"], dict):
            raise ValidationError("accessibility_defaults must be an object.")
        if "name" in changes and not str(name).strip():
            raise ValidationError("Organization name cannot be empty.")

        if name != org["name"]:
            clash = self.orgs_repo.get_by_name(name)
            if clash and clash["id"] != organization_id:
                raise ConflictError(f"An organization named '{name}' already exists.")

        try:
            self.orgs_repo.update_profile(
                organization_id=organization_id,
                name=name,
                organization_type=changes.get(
                    "organization_type", org.get("organization_type") or "industrial_manufacturing"
                ),
                industry=changes.get("industry", org.get("industry") or "Automotive & Aerospace Assembly"),
                location=changes.get("location", org.get("location") or "Main Operations Facility"),
                contact_email=changes.get("contact_email", org.get("contact_email")),
                default_language=changes.get("default_language", org.get("default_language") or "en"),
                supported_languages=changes.get(
                    "supported_languages",
                    list(org["supported_languages"]) if isinstance(org.get("supported_languages"), list)
                    else ["en", "es", "ta", "hi", "de"],
                ),
                accessibility_defaults=changes.get(
                    "accessibility_defaults",
                    dict(org["accessibility_defaults"]) if isinstance(org.get("accessibility_defaults"), dict)
                    else {
                        "default_dwell_time_ms": 500,
                        "high_contrast_default": False,
                        "min_target_size_px": 48,
                        "voice_confirmation_default": False,
                    },
                ),
            )
        except errors.UniqueViolation:
            raise ConflictError(f"An organization named '{name}' already exists.")

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="organization.profile_updated",
            resource_type="organization",
            resource_id=organization_id,
            event_data=changes,
        )

        return self.get_organization_profile(organization_id)

    # 3. Department Management (§ 7, § 8)
    # =========================================================================

    @staticmethod
    def _department_item(row: Dict[str, Any]) -> DepartmentItem:
        return DepartmentItem(
            id=row["id"],
            organization_id=row["organization_id"],
            name=row["name"],
            status=row["status"],
            supervisor_count=int(row.get("supervisor_count") or 0),
            worker_count=int(row.get("worker_count") or 0),
            active_tasks_count=int(row.get("active_tasks_count") or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_departments(self, organization_id: UUID) -> List[DepartmentItem]:
        """List departments with real supervisor/worker/active-task aggregates."""
        rows = self.depts_repo.list_by_organization_with_counts(organization_id)
        return [self._department_item(row) for row in rows]

    def create_department(
        self,
        organization_id: UUID,
        payload: DepartmentCreatePayload,
        actor_id: UUID,
    ) -> DepartmentItem:
        """Create a new department scoped to the organization (409 on duplicate)."""
        existing = self.depts_repo.get_by_name(organization_id, payload.name)
        if existing:
            raise ConflictError(
                f"Department '{payload.name}' already exists in this organization."
            )

        try:
            created = self.depts_repo.create(
                organization_id=organization_id, name=payload.name
            )
        except errors.UniqueViolation as exc:
            raise ConflictError(
                f"Department '{payload.name}' already exists in this organization."
            ) from exc

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="department.created",
            resource_type="department",
            resource_id=created["id"],
            event_data={"name": payload.name, "status": created["status"]},
        )

        counted = self.depts_repo.get_with_counts(created["id"])
        return self._department_item(counted or created)

    def update_department(
        self,
        organization_id: UUID,
        department_id: UUID,
        payload: DepartmentUpdatePayload,
        actor_id: UUID,
    ) -> DepartmentItem:
        """Persist department rename/status changes (previously audit-only)."""
        dept = self.depts_repo.get_by_id(department_id)
        if not dept or dept["organization_id"] != organization_id:
            raise NotFoundError("Department not found in your organization.")

        new_name = payload.name
        status_value = payload.status
        # EntityStatus may be coerced to a plain string by model config.
        new_status = getattr(status_value, "value", status_value) if status_value is not None else None
        if new_name is None and new_status is None:
            raise ValidationError("No changes supplied; provide name and/or status.")

        if new_name is not None and new_name != dept["name"]:
            clash = self.depts_repo.get_by_name(organization_id, new_name)
            if clash and clash["id"] != department_id:
                raise ConflictError(
                    f"Department '{new_name}' already exists in this organization."
                )

        try:
            updated = self.depts_repo.update(
                department_id=department_id, name=new_name, status=new_status
            )
        except errors.UniqueViolation as exc:
            raise ConflictError(
                f"Department '{new_name}' already exists in this organization."
            ) from exc

        if updated is None:
            raise ValidationError("No changes supplied; provide name and/or status.")

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="department.updated",
            resource_type="department",
            resource_id=department_id,
            event_data=payload.model_dump(exclude_unset=True),
        )

        counted = self.depts_repo.get_with_counts(department_id)
        return self._department_item(counted or updated)

    def deactivate_department(
        self,
        organization_id: UUID,
        department_id: UUID,
        actor_id: UUID,
    ) -> Dict[str, Any]:
        """Deactivate department (real status mutation, previously audit-only)."""
        dept = self.depts_repo.get_by_id(department_id)
        if not dept or dept["organization_id"] != organization_id:
            raise NotFoundError("Department not found in your organization.")

        if dept["status"] != "inactive":
            updated = self.depts_repo.update(
                department_id=department_id, status="inactive"
            )
            if updated is None:
                raise ValidationError("Department could not be deactivated.")
            self.audit_repo.create(
                organization_id=organization_id,
                actor_user_id=actor_id,
                event_type="department.deactivated",
                resource_type="department",
                resource_id=department_id,
                event_data={"name": dept["name"], "previous_status": dept["status"]},
            )

        return {
            "message": f"Department '{dept['name']}' has been deactivated.",
            "id": str(department_id),
            "status": "inactive",
        }

    # =========================================================================
    # 4. Supervisor Management (§ 9, § 13)
    # =========================================================================

    def list_supervisors(self, organization_id: UUID) -> List[SupervisorItem]:
        """List supervisors from PostgreSQL with real department and worker counts."""
        rows = self.users_repo.list_organization_supervisors(organization_id)
        return [
            SupervisorItem(
                user_id=row["id"],
                organization_id=organization_id,
                full_name=row["full_name"],
                email=row["email"],
                department_id=row.get("department_id"),
                department_name=row.get("department_name") or "Unassigned",
                status=row["status"],
                assigned_workers_count=int(row.get("assigned_workers_count") or 0),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def invite_supervisor(
        self,
        organization_id: UUID,
        payload: SupervisorInvitePayload,
        actor_id: UUID,
    ) -> SupervisorItem:
        """
        Create a real supervisor account: persists user, department assignment,
        and supervisor role in PostgreSQL. Duplicate email -> ConflictError (409).
        """
        email = payload.email.strip().lower()

        existing = self.users_repo.get_by_email(organization_id, email)
        if existing:
            raise ConflictError(
                f"A user with email '{email}' already exists in this organization."
            )

        dept = None
        if payload.department_id:
            dept = self.depts_repo.get_by_id(payload.department_id)
            if not dept or dept["organization_id"] != organization_id:
                raise ValidationError("Department does not exist in this organization.")

        initial_password = payload.temporary_password or secrets.token_urlsafe(24)
        password_hash = hash_password(initial_password)

        try:
            user = self.users_repo.create(
                organization_id=organization_id,
                email=email,
                full_name=payload.full_name,
                password_hash=password_hash,
            )
        except errors.UniqueViolation as exc:
            raise ConflictError(
                f"A user with email '{email}' already exists in this organization."
            ) from exc

        try:
            if dept:
                self.user_departments_repo.create(
                    user_id=user["id"],
                    department_id=dept["id"],
                )

            supervisor_role = self.roles_repo.get_by_name("supervisor")
            if supervisor_role and not self.user_roles_repo.get(
                user_id=user["id"], role_id=supervisor_role["id"]
            ):
                self.user_roles_repo.create(
                    user_id=user["id"],
                    role_id=supervisor_role["id"],
                )
        except Exception:
            try:
                self.users_repo.delete_by_id(user["id"])
            except Exception:
                pass
            raise

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="supervisor.invited",
            resource_type="user",
            resource_id=user["id"],
            event_data={
                "email": email,
                "full_name": payload.full_name,
                "department": dept["name"] if dept else "Unassigned",
                "notes": payload.notes,
            },
        )

        return SupervisorItem(
            user_id=user["id"],
            organization_id=organization_id,
            full_name=user["full_name"],
            email=user["email"],
            department_id=dept["id"] if dept else None,
            department_name=dept["name"] if dept else "Unassigned",
            status="invited",
            assigned_workers_count=0,
            created_at=user["created_at"],
        )

    def update_supervisor(
        self,
        organization_id: UUID,
        user_id: UUID,
        payload: SupervisorUpdatePayload,
        actor_id: UUID,
    ) -> Dict[str, Any]:
        """Apply real supervisor updates: department reassignment and/or status change."""
        changes: Dict[str, Any] = {}

        if not payload.model_dump(exclude_unset=True):
            raise ValidationError("No changes supplied; provide department_id and/or status.")

        user = self.users_repo.get_by_id(user_id)
        if not user or user["organization_id"] != organization_id:
            raise NotFoundError("Supervisor not found in this organization.")

        supervisor_role = self.roles_repo.get_by_name("supervisor")
        role_links = self.user_roles_repo.get_by_user_id(user_id)
        if not supervisor_role or not any(
            link["role_id"] == supervisor_role["id"] for link in role_links
        ):
            raise NotFoundError("User is not a supervisor in this organization.")

        if payload.department_id is not None:
            dept = self.depts_repo.get_by_id(payload.department_id)
            if not dept or dept["organization_id"] != organization_id:
                raise NotFoundError("Department not found in this organization.")
            for link in self.user_departments_repo.get_by_user_id(user_id):
                self.user_departments_repo.delete(
                    user_id=user_id, department_id=link["department_id"]
                )
            self.user_departments_repo.create(
                user_id=user_id, department_id=dept["id"]
            )
            changes["department_id"] = str(dept["id"])

        if payload.status is not None:
            if payload.status not in ("active", "suspended"):
                raise ValidationError("status must be 'active' or 'suspended'.")
            self.users_repo.update_status(user_id=user_id, status=payload.status)
            changes["status"] = payload.status

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="supervisor.updated",
            resource_type="user",
            resource_id=user_id,
            event_data=changes,
        )
        return {
            "message": "Supervisor details successfully updated.",
            "user_id": str(user_id),
            "changes": changes,
        }

    # =========================================================================
    # 5. Worker Management (§ 10, § 11, § 13)
    # =========================================================================

    def list_workers(
        self,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 25,
        status_filter: Optional[str] = None,
        dept_filter: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """List workers from PostgreSQL with real lifecycle and operational state."""
        rows, total = self.workers_repo.list_enterprise_directory(
            organization_id=organization_id,
            limit=page_size,
            offset=(page - 1) * page_size,
            status_filter=status_filter,
            dept_filter=dept_filter,
        )

        items: List[EnterpriseWorkerItem] = [
            EnterpriseWorkerItem(
                worker_profile_id=row["worker_profile_id"],
                user_id=row["user_id"],
                organization_id=row["organization_id"],
                full_name=row["full_name"],
                email=row["email"],
                badge_number=row.get("badge_number"),
                department_id=row.get("department_id"),
                department_name=row.get("department_name") or "Unassigned",
                # No worker->supervisor assignment model exists yet; "Unassigned"
                # is the honest value (the previous hardcoded roster invented names).
                supervisor_name="Unassigned",
                status=row["lifecycle_status"],
                interaction_mode=row.get("interaction_mode") or "multimodal",
                training_completed=bool(row.get("overall_ready")),
                current_task_name=row.get("current_task_name"),
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return {
            "items": items,
            "total_count": total,
            "page": page,
            "page_size": page_size,
        }

    def invite_worker(
        self,
        organization_id: UUID,
        payload: WorkerInvitePayload,
        actor_id: UUID,
    ) -> EnterpriseWorkerItem:
        """
        Create a real worker invitation: persists the user account, worker
        profile (badge), department assignment, worker role, and readiness
        preferences in PostgreSQL. Duplicate emails yield ConflictError (409).
        """
        email = payload.email.strip().lower()

        existing = self.users_repo.get_by_email(organization_id, email)
        if existing:
            raise ConflictError(
                f"A user with email '{email}' already exists in this organization."
            )

        dept = None
        if payload.department_id:
            dept = self.depts_repo.get_by_id(payload.department_id)
            if not dept or dept["organization_id"] != organization_id:
                raise ValidationError("Department does not exist in this organization.")

        # Initial credential: operator-provided temporary password, otherwise a
        # generated secret. Never returned in the API response.
        initial_password = (payload.temporary_password or secrets.token_urlsafe(24))
        password_hash = hash_password(initial_password)

        try:
            user = self.users_repo.create(
                organization_id=organization_id,
                email=email,
                full_name=payload.full_name,
                password_hash=password_hash,
            )
        except errors.UniqueViolation as exc:
            raise ConflictError(
                f"A user with email '{email}' already exists in this organization."
            ) from exc

        try:
            profile = self.workers_repo.create(
                user["id"],
                badge_number=payload.badge_number,
            )

            if dept:
                self.user_departments_repo.create(
                    user_id=user["id"],
                    department_id=dept["id"],
                )

            worker_role = self.roles_repo.get_by_name("worker")
            if worker_role and not self.user_roles_repo.get(
                user_id=user["id"], role_id=worker_role["id"]
            ):
                self.user_roles_repo.create(
                    user_id=user["id"],
                    role_id=worker_role["id"],
                )

            modality = payload.preferred_modality or "multimodal"
            self.worker_readiness_repo.upsert(
                profile["id"],
                {
                    "is_fresher": True,
                    "onboarding_completed": False,
                    "readiness_status": "incomplete",
                    "interaction_mode": modality,
                    "gesture_ready": False,
                    "voice_ready": False,
                    "multimodal_ready": False,
                    "task_training_complete": False,
                    "overall_ready": False,
                    "completed_stages": [],
                    "active_preferences": {
                        "language": "en",
                        "modality": modality,
                        "dwell_time_ms": 500,
                        "high_contrast": False,
                        "text_scale": 1.0,
                    },
                },
            )
        except Exception:
            # No cross-repository transaction exists at the repository layer;
            # roll back the partially created account so a failed invitation
            # never leaves an orphaned user row.
            try:
                self.users_repo.delete_by_id(user["id"])
            except Exception:
                pass
            raise

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="worker.invited",
            resource_type="worker_profile",
            resource_id=profile["id"],
            event_data={
                "email": email,
                "full_name": payload.full_name,
                "badge_number": payload.badge_number,
                "preferred_modality": payload.preferred_modality,
                "department": dept["name"] if dept else "Unassigned",
            },
        )

        return EnterpriseWorkerItem(
            worker_profile_id=profile["id"],
            user_id=user["id"],
            organization_id=organization_id,
            full_name=user["full_name"],
            email=user["email"],
            badge_number=profile.get("badge_number"),
            department_id=dept["id"] if dept else None,
            department_name=dept["name"] if dept else "Unassigned",
            supervisor_name="Unassigned",
            status="INVITED",
            interaction_mode=payload.preferred_modality or "multimodal",
            training_completed=False,
            current_task_name=None,
            created_at=user["created_at"],
        )

    # =========================================================================
    # 6. Enterprise Workflows & Task Templates (§ 14, § 16)
    # =========================================================================

    def _workflow_item(self, wf_row: Dict[str, Any]) -> WorkflowTemplate:
        """Build a WorkflowTemplate response from database rows."""
        step_rows = self.workflow_steps_repo.list_by_workflow_id(wf_row["id"])
        steps = [
            WorkflowStepItem(
                step_number=row["step_order"],
                title=row["name"],
                instruction=row.get("description") or "",
                is_safety_critical=bool(row.get("is_safety_critical", False)),
                expected_duration_seconds=int(row.get("expected_duration_seconds") or 120),
                required_intent=row.get("required_intent"),
            )
            for row in sorted(step_rows, key=lambda r: r["step_order"])
        ]
        department_id = wf_row.get("department_id")
        department_name = None
        if department_id:
            dept = self.depts_repo.get_by_id(department_id)
            if dept:
                department_name = dept["name"]
        return WorkflowTemplate(
            id=wf_row["id"],
            organization_id=wf_row["organization_id"],
            name=wf_row["name"],
            description=wf_row.get("description"),
            department_id=department_id,
            department_name=department_name,
            version=int(wf_row.get("version") or 1),
            status=wf_row["status"],
            step_count=len(steps),
            estimated_duration_minutes=float(wf_row.get("estimated_duration_minutes") or 15.0),
            steps=steps,
            created_at=wf_row["created_at"],
            updated_at=wf_row["updated_at"],
        )

    @staticmethod
    def _step_spec(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalise one step payload entry."""
        title = (raw.get("title") or "").strip()
        if not title:
            raise ValidationError("Each workflow step requires a title.")
        duration = raw.get("expected_duration_seconds", 120)
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            raise ValidationError("expected_duration_seconds must be an integer.")
        if duration <= 0:
            raise ValidationError("expected_duration_seconds must be positive.")
        intent = raw.get("required_intent")
        if intent is not None:
            intent = str(intent).strip() or None
        return {
            "title": title,
            "instruction": raw.get("instruction") or "",
            "is_safety_critical": bool(raw.get("is_safety_critical", False)),
            "expected_duration_seconds": duration,
            "required_intent": intent,
        }

    def list_workflows(self, organization_id: UUID) -> List[WorkflowTemplate]:
        """List enterprise workflow templates (real rows + their steps)."""
        rows = self.workflows_repo.list_by_organization_id(organization_id)
        return [self._workflow_item(row) for row in rows]

    def create_workflow(
        self,
        organization_id: UUID,
        payload: WorkflowCreatePayload,
        actor_id: UUID,
    ) -> WorkflowTemplate:
        """Define an approved organization assembly workflow template.

        The workflow and every step are persisted to PostgreSQL. A duplicate
        name (pre-check or unique-index race) is a 409 conflict.
        """
        department_id = None
        if payload.department_id:
            dept = self.depts_repo.get_by_id(payload.department_id)
            if not dept or dept["organization_id"] != organization_id:
                raise ValidationError("Unknown department for this organization.")
            department_id = dept["id"]

        specs = [self._step_spec(step) for step in payload.steps]
        estimated = float(payload.estimated_duration_minutes or 15.0)
        if estimated <= 0:
            raise ValidationError("estimated_duration_minutes must be positive.")

        existing = self.workflows_repo.get_by_organization_and_name(organization_id, payload.name)
        if existing:
            raise ConflictError(f"A workflow named '{payload.name}' already exists.")

        workflow_row: Dict[str, Any] | None = None
        created_step_ids: List[UUID] = []
        try:
            workflow_row = self.workflows_repo.create(
                organization_id=organization_id,
                name=payload.name,
                description=payload.description,
                status="active",
                department_id=department_id,
                version=1,
                estimated_duration_minutes=estimated,
            )
            for index, spec in enumerate(specs, start=1):
                step_row = self.workflow_steps_repo.create(
                    workflow_id=workflow_row["id"],
                    step_order=index,
                    name=spec["title"],
                    description=spec["instruction"],
                    status="active",
                    is_safety_critical=spec["is_safety_critical"],
                    expected_duration_seconds=spec["expected_duration_seconds"],
                    required_intent=spec["required_intent"],
                )
                created_step_ids.append(step_row["id"])
        except errors.UniqueViolation:
            # Duplicate (organization_id, name) raced past the pre-check.
            raise ConflictError(f"A workflow named '{payload.name}' already exists.")
        except Exception:
            # Partial failure: remove any rows already written (separate
            # connections per repo call, so no transaction rolls back for us).
            for step_id in created_step_ids:
                try:
                    self.workflow_steps_repo.delete_by_id(step_id)
                except Exception:
                    pass
            if workflow_row is not None:
                try:
                    self.workflows_repo.delete_by_id(workflow_row["id"])
                except Exception:
                    pass
            raise

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="workflow.created",
            resource_type="workflow",
            resource_id=workflow_row["id"],
            event_data={"name": payload.name, "step_count": len(specs)},
        )
        return self._workflow_item(workflow_row)

    def update_workflow(
        self,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowUpdatePayload,
        actor_id: UUID,
    ) -> WorkflowTemplate:
        """Update an approved workflow definition — persisted, not audit-only."""
        wf = self.workflows_repo.get_by_id(workflow_id)
        if not wf or wf["organization_id"] != organization_id:
            raise NotFoundError("Workflow not found.")

        changes = payload.model_dump(exclude_unset=True)
        name = changes.get("name", wf["name"])
        description = changes.get("description", wf.get("description"))
        status_value = changes.get("status", wf["status"])
        if status_value not in ("active", "inactive", "archived"):
            raise ValidationError("status must be one of: active, inactive, archived.")

        department_id = wf.get("department_id")
        if "department_id" in changes:
            new_dept = changes["department_id"]
            if new_dept is None:
                department_id = None
            else:
                dept = self.depts_repo.get_by_id(new_dept)
                if not dept or dept["organization_id"] != organization_id:
                    raise ValidationError("Unknown department for this organization.")
                department_id = dept["id"]

        if "name" in changes and name != wf["name"]:
            clash = self.workflows_repo.get_by_organization_and_name(organization_id, name)
            if clash and clash["id"] != workflow_id:
                raise ConflictError(f"A workflow named '{name}' already exists.")

        try:
            updated = self.workflows_repo.update(
                workflow_id,
                name=name,
                description=description,
                status=status_value,
                department_id=department_id,
                version=int(wf.get("version") or 1) + 1,
                estimated_duration_minutes=wf.get("estimated_duration_minutes") or 15.0,
            )
        except errors.UniqueViolation:
            raise ConflictError(f"A workflow named '{name}' already exists.")
        if not updated:
            raise NotFoundError("Workflow not found.")

        step_count = None
        if changes.get("steps") is not None:
            specs = [self._step_spec(step) for step in changes["steps"]]
            self._replace_steps(workflow_id, specs)
            step_count = len(specs)

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="workflow.updated",
            resource_type="workflow",
            resource_id=workflow_id,
            event_data={
                "changed": sorted(changes.keys()),
                "step_count": step_count,
            },
        )
        return self._workflow_item(updated)

    def _replace_steps(self, workflow_id: UUID, specs: List[Dict[str, Any]]) -> None:
        """Sync workflow_steps to exactly ``specs`` (ordered 1..N).

        Steps with execution history cannot be removed — the foreign key
        surfaces that as a 409 instead of silent data loss.
        """
        existing = self.workflow_steps_repo.list_by_workflow_id(workflow_id)
        by_order = {row["step_order"]: row for row in existing}

        try:
            for order in sorted(by_order):
                if order > len(specs):
                    self.workflow_steps_repo.delete_by_id(by_order[order]["id"])
            for index, spec in enumerate(specs, start=1):
                match = by_order.get(index)
                if match:
                    self.workflow_steps_repo.update(
                        match["id"],
                        step_order=index,
                        name=spec["title"],
                        description=spec["instruction"],
                        status="active",
                        is_safety_critical=spec["is_safety_critical"],
                        expected_duration_seconds=spec["expected_duration_seconds"],
                        required_intent=spec["required_intent"],
                    )
                else:
                    self.workflow_steps_repo.create(
                        workflow_id=workflow_id,
                        step_order=index,
                        name=spec["title"],
                        description=spec["instruction"],
                        status="active",
                        is_safety_critical=spec["is_safety_critical"],
                        expected_duration_seconds=spec["expected_duration_seconds"],
                        required_intent=spec["required_intent"],
                    )
        except errors.ForeignKeyViolation:
            raise ConflictError(
                "Workflow steps with execution history cannot be removed. "
                "Create a new workflow instead."
            )

    # =========================================================================
    # 7. Assistance Overview & Emergency Events (§ 19, § 20)
    # =========================================================================

    def get_assistance_overview(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """Organization-wide assistance activity from assistance_requests rows."""
        rows = self.assistance_repo.list_by_organization_id(organization_id)
        overview: List[Dict[str, Any]] = []
        for r in rows:
            worker = self.workers_repo.get_by_id(r["worker_profile_id"])
            user = self.users_repo.get_by_id(worker["user_id"]) if worker else None
            worker_name = None
            if user:
                worker_name = user.get("full_name") or user.get("email")

            department_name = None
            if user:
                link = self.user_departments_repo.get_by_user_id(user["id"])
                if link:
                    dept = self.depts_repo.get_by_id(link[0]["department_id"])
                    if dept:
                        department_name = dept["name"]

            task_name = None
            if r.get("worker_task_assignment_id"):
                assignment = self.worker_task_assignments_repo.get_by_id(
                    r["worker_task_assignment_id"]
                )
                if assignment:
                    task = self.tasks_repo.get_by_id(assignment["task_id"])
                    if task:
                        task_name = task.get("name")

            reason = r.get("reason") or ""
            is_emergency = (
                r.get("priority") == "urgent" or "emergency" in reason.lower()
            )
            overview.append({
                "id": str(r["id"]),
                "worker_name": worker_name,
                "department_name": department_name,
                "supervisor_name": None,  # no supervisor column exists; honest null
                "task_name": task_name,
                "priority": r.get("priority"),
                "reason": reason or None,
                "status": r.get("status"),
                "requested_at": r["requested_at"].isoformat() if r.get("requested_at") else None,
                "resolved_at": r["resolved_at"].isoformat() if r.get("resolved_at") else None,
                "is_emergency": is_emergency,
            })
        return overview

    def get_emergency_events(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """Active emergency safety halt events from assistance_requests (urgent + open)."""
        return [
            e for e in self.get_assistance_overview(organization_id)
            if e.get("is_emergency")
            and e.get("status") in ("open", "acknowledged", "in_progress")
        ]

    # 8. Operational & Accessibility Analytics (§ 21, § 22)
    # =========================================================================

    def get_organization_analytics(self, organization_id: UUID) -> OrganizationAnalyticsSummary:
        """Aggregate operational + accessibility analytics from PostgreSQL.

        Previously tasks_completed_count=19, tasks_in_progress_count=3,
        average_task_duration_minutes=8.2, workflow_completion_rate=94.5,
        total_assistance_requests=6, average_resolution_time_minutes=1.5 and
        emergency_stops_count=0 were hardcoded constants. Every value is now
        computed from real rows.
        """
        workers = self.list_workers(organization_id, page=1, page_size=500)["items"]
        total = len(workers)
        active = sum(1 for w in workers if w.status not in ("DEACTIVATED", "INVITED"))

        gesture_ready = sum(1 for w in workers if w.interaction_mode in ("gesture", "multimodal"))
        voice_ready = sum(1 for w in workers if w.interaction_mode in ("voice", "multimodal"))
        multi_ready = sum(1 for w in workers if w.interaction_mode == "multimodal")
        needing_training = sum(1 for w in workers if not w.training_completed)

        # Task metrics from real assignments
        assigned_count = 0
        completed_count = 0
        in_progress_count = 0
        durations: List[float] = []
        for task in self.tasks_repo.list_by_organization_id(organization_id):
            for a in self.worker_task_assignments_repo.list_by_task_id(task["id"]):
                assigned_count += 1
                st = a.get("status")
                if st == "completed":
                    completed_count += 1
                    if a.get("started_at") and a.get("completed_at"):
                        dur = (a["completed_at"] - a["started_at"]).total_seconds() / 60.0
                        durations.append(dur)
                elif st in ("in_progress", "assigned", "paused"):
                    in_progress_count += 1

        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0
        completion_rate = (
            round((completed_count / assigned_count) * 100.0, 1) if assigned_count else 0.0
        )

        # Assistance metrics from real rows
        assistance_rows = self.assistance_repo.list_by_organization_id(organization_id)
        total_assistance = len(assistance_rows)
        resolution_times: List[float] = []
        emergency_count = 0
        for r in assistance_rows:
            if r.get("resolved_at") and r.get("requested_at"):
                delta = r["resolved_at"] - r["requested_at"]
                resolution_times.append(delta.total_seconds() / 60.0)
            reason = (r.get("reason") or "").lower()
            if (
                r.get("priority") == "urgent" or "emergency" in reason
            ) and r.get("status") in ("open", "acknowledged", "in_progress"):
                emergency_count += 1
        avg_resolution = (
            round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0
        )

        return OrganizationAnalyticsSummary(
            organization_id=organization_id,
            total_workers=total,
            active_workers=active,
            tasks_completed_count=completed_count,
            tasks_in_progress_count=in_progress_count,
            average_task_duration_minutes=avg_duration,
            workflow_completion_rate=completion_rate,
            total_assistance_requests=total_assistance,
            average_resolution_time_minutes=avg_resolution,
            emergency_stops_count=emergency_count,
            gesture_ready_workers_count=gesture_ready,
            voice_ready_workers_count=voice_ready,
            multimodal_ready_workers_count=multi_ready,
            workers_needing_training_count=needing_training,
        )

    # 9. Immutable Audit Log Trail (§ 23)
    # =========================================================================

    def query_audit_logs(self, organization_id: UUID, limit: int = 50) -> List[OrganizationAuditEventItem]:
        """Query append-only immutable audit trail for the organization.

        Actor names/roles are resolved from the users and user_roles tables
        (never fabricated), and an empty trail returns an empty list instead
        of a seeded fake stream.
        """
        records = self.audit_repo.list_by_organization_id(organization_id)
        records = list(records)[: max(1, limit)]
        now = datetime.now(timezone.utc)

        actor_cache: Dict[Any, tuple] = {}

        def _actor(uid: Any) -> tuple:
            if uid is None:
                return ("system", "system")
            if uid in actor_cache:
                return actor_cache[uid]
            user = self.users_repo.get_by_id(uid) if uid else None
            if user:
                name = user.get("full_name") or user.get("email") or str(uid)
            else:
                name = "deleted user"
            role = "user"
            assignments = self.user_roles_repo.get_by_user_id(uid)
            if assignments:
                role_row = self.roles_repo.get_by_id(assignments[0]["role_id"])
                if role_row:
                    role = role_row.get("name") or "user"
            actor_cache[uid] = (name, role)
            return actor_cache[uid]

        items: List[OrganizationAuditEventItem] = []
        for r in records:
            actor_name, actor_role = _actor(r.get("actor_user_id"))
            items.append(
                OrganizationAuditEventItem(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    actor_name=actor_name,
                    actor_role=actor_role,
                    event_type=r["event_type"],
                    resource_type=r["resource_type"],
                    resource_id=r.get("resource_id"),
                    occurred_at=r.get("occurred_at") or r.get("created_at") or now,
                    event_data=r.get("event_data") or {},
                )
            )
        return items
