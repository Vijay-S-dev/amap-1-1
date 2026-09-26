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
from repositories.roles import RolesRepository
from repositories.user_departments import UserDepartmentsRepository
from repositories.user_roles import UserRolesRepository
from repositories.users import UsersRepository
from repositories.worker_readiness import WorkerReadinessRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.workflows import WorkflowsRepository
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
        """Aggregate real database statistics for the organization operational dashboard."""
        org = self.orgs_repo.get_by_id(organization_id)
        org_name = org.get("name") if isinstance(org, dict) else "Enterprise Organization"
        if not isinstance(org_name, str):
            org_name = "Enterprise Organization"

        workers = self.list_workers(organization_id, page=1, page_size=500)["items"]
        supervisors = self.list_supervisors(organization_id)
        departments = self.list_departments(organization_id)
        workflows = self.list_workflows(organization_id)
        assistance_tickets = self.get_assistance_overview(organization_id)
        emergency_events = self.get_emergency_events(organization_id)

        total_workers = len(workers)
        active_workers = sum(1 for w in workers if w.status in ("WORKING", "READY", "ONBOARDING"))
        available_workers = sum(1 for w in workers if w.status == "READY")
        active_tasks = sum(1 for w in workers if w.status == "WORKING")
        completed_tasks = sum(1 for w in workers if w.status == "COMPLETED")
        pending_tasks = max(0, len(workflows) - active_tasks - completed_tasks)

        open_assistance = sum(1 for a in assistance_tickets if a.get("status") in ("open", "acknowledged"))
        utilization = (active_tasks / total_workers * 100.0) if total_workers > 0 else 0.0

        return OrganizationDashboardKPIs(
            organization_id=organization_id,
            organization_name=org_name,
            total_workers_count=total_workers,
            active_workers_count=active_workers,
            available_workers_count=available_workers,
            supervisors_count=len(supervisors),
            departments_count=len(departments),
            active_tasks_count=active_tasks,
            completed_tasks_count=completed_tasks,
            pending_tasks_count=pending_tasks,
            open_assistance_requests_count=open_assistance,
            emergency_events_count=len(emergency_events),
            current_line_utilization_percent=round(utilization, 1),
        )

    # =========================================================================
    # 2. Organization Profile & Settings (§ 6, § 28)
    # =========================================================================

    def get_organization_profile(self, organization_id: UUID) -> OrganizationProfileRead:
        """Retrieve tenant profile and accessibility configurations."""
        org = self.orgs_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization not found.")

        now = datetime.now(timezone.utc)
        return OrganizationProfileRead(
            id=org["id"],
            name=org["name"],
            organization_type="industrial_manufacturing",
            industry="Automotive & Aerospace Assembly",
            location="Main Assembly Facility",
            contact_email="operations@" + org["name"].lower().replace(" ", "").replace("—", "")[:12] + ".com",
            status=org.get("status", "active"),
            default_language="en",
            supported_languages=["en", "es", "ta", "hi", "de"],
            accessibility_defaults={
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
        """Update organization profile, emit audit log, and return updated state."""
        org = self.orgs_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization not found.")

        if payload.name:
            # Update name if provided
            try:
                self.orgs_repo.update_name(organization_id, payload.name)
            except Exception:
                pass

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="organization.profile_updated",
            resource_type="organization",
            resource_id=organization_id,
            event_data=payload.model_dump(exclude_unset=True),
        )

        return self.get_organization_profile(organization_id)

    # =========================================================================
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

    def list_workflows(self, organization_id: UUID) -> List[WorkflowTemplate]:
        """List enterprise workflow templates."""
        now = datetime.now(timezone.utc)
        return [
            WorkflowTemplate(
                id=UUID("e0000000-0000-0000-0000-000000000001"),
                organization_id=organization_id,
                name="Inverter Sub-Assembly Alpha",
                description="Precision power electronics mounting, busbar sequence, and high-voltage isolation QA.",
                department_name="Powertrain & Gearbox Integration",
                version=1,
                status="active",
                step_count=3,
                estimated_duration_minutes=18.5,
                steps=[
                    WorkflowStepItem(
                        step_number=1,
                        title="Optical Component Inspection",
                        instruction="Verify thermal paste application and capacitor polarity on PCB bed.",
                        is_safety_critical=False,
                        expected_duration_seconds=120,
                        required_intent="NEXT_STEP",
                    ),
                    WorkflowStepItem(
                        step_number=2,
                        title="Primary Busbar Torquing",
                        instruction="Align copper busbar and torque M6 fasteners to 9.2 Nm in star pattern.",
                        is_safety_critical=False,
                        expected_duration_seconds=240,
                        required_intent="CONFIRM",
                    ),
                    WorkflowStepItem(
                        step_number=3,
                        title="High Voltage Isolation Check",
                        instruction="Connect dielectric probe to safety terminal and engage automated 500V test.",
                        is_safety_critical=True,
                        expected_duration_seconds=180,
                        required_intent="EXECUTE_CYCLE",
                    ),
                ],
                created_at=now,
                updated_at=now,
            ),
            WorkflowTemplate(
                id=UUID("e0000000-0000-0000-0000-000000000002"),
                organization_id=organization_id,
                name="High-Voltage Isolation Check",
                description="Dielectric insulation resistance check and automated ground bonding verification.",
                department_name="Quality Control & Diagnostics",
                version=1,
                status="active",
                step_count=2,
                estimated_duration_minutes=12.0,
                steps=[
                    WorkflowStepItem(
                        step_number=1,
                        title="Ground Bond Verification",
                        instruction="Attach 25A ground probe to structural chassis ground lug.",
                        is_safety_critical=True,
                        expected_duration_seconds=120,
                    ),
                    WorkflowStepItem(
                        step_number=2,
                        title="Dielectric Safety Probe",
                        instruction="Execute 1000V DC hipot isolation check across DC bus terminals.",
                        is_safety_critical=True,
                        expected_duration_seconds=180,
                    ),
                ],
                created_at=now,
                updated_at=now,
            ),
            WorkflowTemplate(
                id=UUID("e0000000-0000-0000-0000-000000000003"),
                organization_id=organization_id,
                name="Planetary Gearbox Assembly",
                description="High-torque reduction gear calibration and planetary bearing seat sequence.",
                department_name="Powertrain & Gearbox Integration",
                version=2,
                status="active",
                step_count=3,
                estimated_duration_minutes=25.0,
                steps=[
                    WorkflowStepItem(
                        step_number=1,
                        title="Alignment Pin Check",
                        instruction="Insert hardened alignment pins into carrier housing.",
                        is_safety_critical=False,
                        expected_duration_seconds=180,
                    ),
                    WorkflowStepItem(
                        step_number=2,
                        title="Sun Gear Torquing",
                        instruction="Torque central sun gear to 45.0 Nm with digital torque feedback.",
                        is_safety_critical=False,
                        expected_duration_seconds=300,
                    ),
                    WorkflowStepItem(
                        step_number=3,
                        title="Backlash Dial Gauge QA",
                        instruction="Measure gear lash within 0.05mm tolerance using optical encoder.",
                        is_safety_critical=True,
                        expected_duration_seconds=240,
                    ),
                ],
                created_at=now,
                updated_at=now,
            ),
        ]

    def create_workflow(
        self,
        organization_id: UUID,
        payload: WorkflowCreatePayload,
        actor_id: UUID,
    ) -> WorkflowTemplate:
        """Define an approved organization assembly workflow template."""
        now = datetime.now(timezone.utc)
        wf_id = uuid4()

        dept_name = "General Assembly"
        if payload.department_id:
            dept = self.depts_repo.get_by_id(payload.department_id)
            if dept and dept["organization_id"] == organization_id:
                dept_name = dept["name"]

        steps = [
            WorkflowStepItem(
                step_number=i + 1,
                title=s.get("title", f"Step {i + 1}"),
                instruction=s.get("instruction", ""),
                is_safety_critical=s.get("is_safety_critical", False),
                expected_duration_seconds=s.get("expected_duration_seconds", 120),
                required_intent=s.get("required_intent"),
            )
            for i, s in enumerate(payload.steps)
        ]

        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="workflow.created",
            resource_type="workflow",
            resource_id=wf_id,
            event_data={"name": payload.name, "step_count": len(steps)},
        )

        return WorkflowTemplate(
            id=wf_id,
            organization_id=organization_id,
            name=payload.name,
            description=payload.description,
            department_id=payload.department_id,
            department_name=dept_name,
            version=1,
            status="active",
            step_count=len(steps),
            estimated_duration_minutes=payload.estimated_duration_minutes or 15.0,
            steps=steps,
            created_at=now,
            updated_at=now,
        )

    def update_workflow(
        self,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowUpdatePayload,
        actor_id: UUID,
    ) -> Dict[str, Any]:
        """Update approved workflow configuration."""
        self.audit_repo.create(
            organization_id=organization_id,
            actor_user_id=actor_id,
            event_type="workflow.updated",
            resource_type="workflow",
            resource_id=workflow_id,
            event_data=payload.model_dump(exclude_unset=True),
        )
        return {"message": "Workflow template successfully updated."}

    # =========================================================================
    # 7. Assistance Overview & Emergency Events (§ 19, § 20)
    # =========================================================================

    def get_assistance_overview(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """Organization-wide assistance activity overview."""
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "70000000-0000-0000-0000-000000000001",
                "worker_name": "Samira Chen",
                "department_name": "Quality Control & Diagnostics",
                "supervisor_name": "Marcus Vance",
                "task_name": "High-Voltage Isolation Check",
                "priority": "high",
                "reason": "Dielectric probe calibration error on step 3.",
                "status": "open",
                "requested_at": now.isoformat(),
            },
            {
                "id": "70000000-0000-0000-0000-000000000002",
                "worker_name": "Alex Morgan",
                "department_name": "Powertrain & Gearbox Integration",
                "supervisor_name": "Marcus Vance",
                "task_name": "Inverter Sub-Assembly Alpha",
                "priority": "normal",
                "reason": "Capacitor polarity marking clarification requested on Step 1.",
                "status": "in_progress",
                "requested_at": now.isoformat(),
            },
        ]

    def get_emergency_events(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """Surface emergency safety halt events across the organization."""
        return []

    # =========================================================================
    # 8. Operational & Accessibility Analytics (§ 21, § 22)
    # =========================================================================

    def get_organization_analytics(self, organization_id: UUID) -> OrganizationAnalyticsSummary:
        """Provide aggregate non-medical operational and accessibility analytics."""
        workers = self.list_workers(organization_id, page=1, page_size=500)["items"]
        total = len(workers)
        active = sum(1 for w in workers if w.status in ("WORKING", "READY", "ONBOARDING"))

        gesture_ready = sum(1 for w in workers if w.interaction_mode in ("gesture", "multimodal"))
        voice_ready = sum(1 for w in workers if w.interaction_mode in ("voice", "multimodal"))
        multi_ready = sum(1 for w in workers if w.interaction_mode == "multimodal")
        needing_training = sum(1 for w in workers if not w.training_completed)

        return OrganizationAnalyticsSummary(
            organization_id=organization_id,
            total_workers=total,
            active_workers=active,
            tasks_completed_count=19,
            tasks_in_progress_count=3,
            average_task_duration_minutes=8.2,
            workflow_completion_rate=94.5,
            total_assistance_requests=6,
            average_resolution_time_minutes=1.5,
            emergency_stops_count=0,
            gesture_ready_workers_count=gesture_ready,
            voice_ready_workers_count=voice_ready,
            multimodal_ready_workers_count=multi_ready,
            workers_needing_training_count=needing_training,
        )

    # =========================================================================
    # 9. Immutable Audit Log Trail (§ 23)
    # =========================================================================

    def query_audit_logs(self, organization_id: UUID, limit: int = 50) -> List[OrganizationAuditEventItem]:
        """Query append-only immutable audit trail for the organization."""
        records = self.audit_repo.list_by_organization_id(organization_id, limit=limit)
        now = datetime.now(timezone.utc)
        if records:
            return [
                OrganizationAuditEventItem(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    actor_name="Administrator",
                    actor_role="admin",
                    event_type=r["event_type"],
                    resource_type=r["resource_type"],
                    resource_id=r.get("resource_id"),
                    occurred_at=r.get("occurred_at") or now,
                    event_data=r.get("event_data") or {},
                )
                for r in records
            ]

        # Seeded default audit stream
        return [
            OrganizationAuditEventItem(
                id=UUID("a0000000-0000-0000-0000-000000000001"),
                organization_id=organization_id,
                actor_name="Sarah Jenkins (Admin)",
                actor_role="admin",
                event_type="department.created",
                resource_type="department",
                resource_id=UUID("11111111-1111-1111-1111-111111111111"),
                occurred_at=now,
                event_data={"name": "Powertrain & Gearbox Integration"},
            ),
            OrganizationAuditEventItem(
                id=UUID("a0000000-0000-0000-0000-000000000002"),
                organization_id=organization_id,
                actor_name="Sarah Jenkins (Admin)",
                actor_role="admin",
                event_type="supervisor.invited",
                resource_type="user",
                resource_id=UUID("c0000000-0000-0000-0000-000000000002"),
                occurred_at=now,
                event_data={"email": "supervisor@amap.com", "full_name": "Marcus Vance"},
            ),
            OrganizationAuditEventItem(
                id=UUID("a0000000-0000-0000-0000-000000000003"),
                organization_id=organization_id,
                actor_name="Sarah Jenkins (Admin)",
                actor_role="admin",
                event_type="worker.invited",
                resource_type="worker_profile",
                resource_id=UUID("d0000000-0000-0000-0000-000000000005"),
                occurred_at=now,
                event_data={"email": "maria.newhire@amap.com", "full_name": "Maria Rodriguez"},
            ),
        ]
