"""
Supervisor and Fleet Operations Service for AMAP.

Provides business logic for supervisor monitoring, multi-tenant organization isolation,
worker inspection, task dispatching, assistance queue resolution, operational analytics,
and immutable audit logging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from models.supervisor import (
    AssistanceResolvePayload,
    AssistanceResponsePayload,
    SupervisorAnalytics,
    SupervisorAuditEvent,
    SupervisorDashboardSummary,
    SupervisorWorkerDetail,
    SupervisorWorkerItem,
    TaskAssignmentPayload,
    TaskReassignmentPayload,
)
from repositories.assistance_requests import AssistanceRequestsRepository
from repositories.audit_events import AuditEventsRepository
from repositories.interaction_configurations import InteractionConfigurationsRepository
from repositories.task_results import TaskResultsRepository
from repositories.task_workflows import TaskWorkflowsRepository
from repositories.tasks import TasksRepository
from repositories.users import UsersRepository
from repositories.worker_readiness import WorkerReadinessRepository
from repositories.work_sessions import WorkSessionsRepository
from repositories.worker_personalizations import WorkerPersonalizationsRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_task_assignments import WorkerTaskAssignmentsRepository
from repositories.workflow_assignments import WorkflowAssignmentsRepository
from repositories.workflow_step_executions import WorkflowStepExecutionsRepository
from repositories.workflow_steps import WorkflowStepsRepository
from repositories.workflows import WorkflowsRepository
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class SupervisorService:
    """Business operations for supervisor and operations management."""

    def __init__(
        self,
        users_repo: Optional[UsersRepository] = None,
        worker_profiles_repo: Optional[WorkerProfilesRepository] = None,
        work_sessions_repo: Optional[WorkSessionsRepository] = None,
        tasks_repo: Optional[TasksRepository] = None,
        worker_task_assignments_repo: Optional[WorkerTaskAssignmentsRepository] = None,
        workflow_assignments_repo: Optional[WorkflowAssignmentsRepository] = None,
        workflows_repo: Optional[WorkflowsRepository] = None,
        workflow_steps_repo: Optional[WorkflowStepsRepository] = None,
        assistance_requests_repo: Optional[AssistanceRequestsRepository] = None,
        audit_events_repo: Optional[AuditEventsRepository] = None,
        interaction_configs_repo: Optional[InteractionConfigurationsRepository] = None,
        worker_personalizations_repo: Optional[WorkerPersonalizationsRepository] = None,
        task_workflows_repo: Optional[TaskWorkflowsRepository] = None,
        step_executions_repo: Optional[WorkflowStepExecutionsRepository] = None,
        worker_readiness_repo: Optional[WorkerReadinessRepository] = None,
        task_results_repo: Optional[TaskResultsRepository] = None,
    ) -> None:
        self.users_repo = users_repo or UsersRepository()
        self.worker_profiles_repo = worker_profiles_repo or WorkerProfilesRepository()
        self.work_sessions_repo = work_sessions_repo or WorkSessionsRepository()
        self.tasks_repo = tasks_repo or TasksRepository()
        self.worker_task_assignments_repo = worker_task_assignments_repo or WorkerTaskAssignmentsRepository()
        self.workflow_assignments_repo = workflow_assignments_repo or WorkflowAssignmentsRepository()
        self.workflows_repo = workflows_repo or WorkflowsRepository()
        self.workflow_steps_repo = workflow_steps_repo or WorkflowStepsRepository()
        self.assistance_requests_repo = assistance_requests_repo or AssistanceRequestsRepository()
        self.audit_events_repo = audit_events_repo or AuditEventsRepository()
        self.interaction_configs_repo = interaction_configs_repo or InteractionConfigurationsRepository()
        self.worker_personalizations_repo = worker_personalizations_repo or WorkerPersonalizationsRepository()
        self.task_workflows_repo = task_workflows_repo or TaskWorkflowsRepository()
        self.step_executions_repo = step_executions_repo or WorkflowStepExecutionsRepository()
        self.worker_readiness_repo = worker_readiness_repo or WorkerReadinessRepository()
        self.task_results_repo = task_results_repo or TaskResultsRepository()

    def _worker_workflow_progress(self, worker_profile_id: UUID, task_id: UUID) -> Optional[Dict[str, Any]]:
        """Derive real workflow step progress for a worker's active task.

        Chain: task -> task_workflows link -> workflow -> workflow_assignments
        (worker) -> workflow_step_executions. Returns None when the task has no
        linked workflow or no steps, so callers show honest empty values instead
        of invented progress.
        """
        tw_links = self.task_workflows_repo.list_by_task_id(task_id)
        if not tw_links:
            return None
        workflow_id = tw_links[0].get("workflow_id")
        if not workflow_id:
            return None

        steps = self.workflow_steps_repo.list_by_workflow_id(workflow_id)
        if not steps:
            return None

        wf_assignment = None
        wf_candidates = [
            wa for wa in self.workflow_assignments_repo.list_by_worker_profile_id(worker_profile_id)
            if wa.get("workflow_id") == workflow_id
        ]
        active_candidates = [
            wa for wa in wf_candidates
            if wa.get("status") in ("assigned", "in_progress", "paused")
        ]
        if active_candidates:
            # current cycle: prefer the one in progress
            wf_assignment = next(
                (wa for wa in active_candidates if wa.get("status") == "in_progress"),
                active_candidates[0],
            )
        elif wf_candidates:
            # fall back to the most recent cycle (e.g. completed assignments)
            wf_assignment = sorted(
                wf_candidates,
                key=lambda wa: wa.get("created_at") or wa.get("assigned_at"),
            )[-1]

        completed_ids: set = set()
        if wf_assignment:
            executions = self.step_executions_repo.list_by_workflow_assignment_id(wf_assignment["id"])
            completed_ids = {
                e["workflow_step_id"] for e in executions if e.get("status") == "completed"
            }

        completed_count = sum(1 for s in steps if s["id"] in completed_ids)
        current_step = None
        current_number = None
        for idx, step in enumerate(steps, 1):
            if step["id"] not in completed_ids:
                current_step = step
                current_number = idx
                break

        return {
            "workflow_id": workflow_id,
            "workflow_assignment_id": wf_assignment["id"] if wf_assignment else None,
            "steps": steps,
            "completed_ids": completed_ids,
            "completed_count": completed_count,
            "total_steps": len(steps),
            "progress_percent": round((completed_count / len(steps)) * 100.0, 1),
            "current_step": current_step,
            "current_step_number": current_number,
        }

    def get_dashboard_summary(self, organization_id: UUID) -> SupervisorDashboardSummary:
        """
        Compute real-time operational dashboard KPIs for the supervisor's organization.
        Derived strictly from actual database state.
        """
        workers = self.list_organization_workers(organization_id)
        active_count = 0
        available_count = 0
        in_task_count = 0
        assistance_count = 0
        emergency_count = 0

        for w in workers:
            if w.status != "OFFLINE":
                active_count += 1
            if w.status == "AVAILABLE":
                available_count += 1
            elif w.status in ("WORKING", "PAUSED"):
                in_task_count += 1
            if w.has_open_assistance or w.status == "ASSISTANCE_REQUESTED":
                assistance_count += 1
            if w.is_emergency_stop:
                emergency_count += 1

        # Count completed and in-progress tasks across all workers in organization
        all_tasks = self.tasks_repo.list_by_organization_id(organization_id) if hasattr(self.tasks_repo, "list_by_organization_id") else []
        completed_tasks = 0
        in_progress_tasks = 0
        failed_tasks = 0

        for task in all_tasks:
            assignments = self.worker_task_assignments_repo.list_by_task_id(task["id"])
            for a in assignments:
                st = a.get("status")
                if st == "completed":
                    completed_tasks += 1
                elif st in ("in_progress", "assigned"):
                    in_progress_tasks += 1
                elif st in ("failed", "cancelled"):
                    failed_tasks += 1

        workload_pct = round(
            (in_task_count / max(1, active_count)) * 100.0 if active_count > 0 else 0.0,
            1,
        )

        return SupervisorDashboardSummary(
            active_workers_count=active_count,
            available_workers_count=available_count,
            workers_in_task_count=in_task_count,
            workers_requesting_assistance_count=assistance_count,
            completed_tasks_count=completed_tasks,
            in_progress_tasks_count=in_progress_tasks,
            failed_tasks_count=failed_tasks,
            current_workload_percent=workload_pct,
            emergency_stops_active=emergency_count,
        )

    def list_organization_workers(self, organization_id: UUID) -> List[SupervisorWorkerItem]:
        """
        List all workers in the supervisor's organization with live status,
        active task progression, and interaction readiness health.
        """
        users = self.users_repo.list_by_organization(organization_id)
        result: List[SupervisorWorkerItem] = []

        for user in users:
            worker_profile = self.worker_profiles_repo.get_by_user_id(user["id"])
            if not worker_profile:
                continue

            wp_id = worker_profile["id"]

            # 1. Check active work session
            sessions = self.work_sessions_repo.list_by_worker_profile_id(wp_id)
            active_session = next((s for s in sessions if s.get("status") == "active"), None)

            session_duration = 0
            if active_session and active_session.get("started_at"):
                started = active_session["started_at"]
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                session_duration = int((datetime.now(timezone.utc) - started).total_seconds())

            # 2. Check active task assignment — prefer work actually in
            # progress, otherwise the most recently created open assignment.
            assignments = self.worker_task_assignments_repo.list_by_worker_profile_id(wp_id)
            active_candidates = sorted(
                (
                    a for a in assignments
                    if a.get("status") in ("in_progress", "assigned", "paused")
                ),
                key=lambda a: a.get("created_at") or a.get("assigned_at"),
                reverse=True,
            )
            active_assignment = next(
                (a for a in active_candidates if a.get("status") == "in_progress"),
                None,
            ) or (active_candidates[0] if active_candidates else None)

            current_task_id = None
            current_task_name = None
            current_assignment_id = None
            progress_percent = 0.0
            current_step_title = None
            current_step_num = None
            total_steps = None

            if active_assignment:
                current_assignment_id = active_assignment["id"]
                current_task_id = active_assignment["task_id"]
                task = self.tasks_repo.get_by_id(current_task_id)
                if task:
                    current_task_name = task.get("name")

                # Real workflow/step tracking from task_workflows ->
                # workflow_assignments -> workflow_step_executions.
                progress = self._worker_workflow_progress(wp_id, current_task_id)
                if progress:
                    total_steps = progress["total_steps"]
                    progress_percent = progress["progress_percent"]
                    current_step = progress["current_step"]
                    if current_step is not None:
                        current_step_title = current_step.get("name") or current_step.get("title")
                        current_step_num = progress["current_step_number"]
                    elif active_assignment.get("status") == "completed":
                        current_step_title = None
                        current_step_num = None

            # 3. Check assistance requests
            all_requests = self.assistance_requests_repo.list_by_worker_profile_id(wp_id)
            open_requests = [
                r for r in all_requests if r.get("status") in ("open", "acknowledged", "in_progress")
            ]
            has_open_assistance = len(open_requests) > 0
            is_emergency = any(
                r.get("priority") == "urgent" or "emergency" in (r.get("reason") or "").lower()
                for r in open_requests
            )

            # 4. Compute status
            status = "OFFLINE"
            if is_emergency or has_open_assistance:
                status = "ASSISTANCE_REQUESTED"
            elif active_session:
                if active_assignment:
                    status = "PAUSED" if active_assignment.get("status") == "paused" else "WORKING"
                else:
                    status = "AVAILABLE"
            else:
                recent_done = [a for a in assignments if a.get("status") == "completed"]
                if recent_done:
                    status = "COMPLETED"

            # 5. Interaction mode + readiness health — sourced from the
            # worker_readiness table (onboarding validation), NOT hardcoded.
            readiness = self.worker_readiness_repo.get(wp_id)
            personalization = self.worker_personalizations_repo.get_by_worker_profile_id(wp_id)
            interaction_mode = "multimodal"
            if readiness and readiness.get("interaction_mode"):
                interaction_mode = readiness["interaction_mode"]
            elif personalization:
                pref = personalization.get("preferences") or {}
                interaction_mode = pref.get("preferred_modality", "multimodal")

            interaction_health = {
                "gesture_ready": bool(readiness and readiness.get("gesture_ready")),
                "voice_ready": bool(readiness and readiness.get("voice_ready")),
                "multimodal_ready": bool(readiness and readiness.get("multimodal_ready")),
            }

            item = SupervisorWorkerItem(
                worker_profile_id=wp_id,
                user_id=user["id"],
                full_name=user.get("full_name") or user["email"],
                email=user["email"],
                status=status,
                current_task_id=current_task_id,
                current_task_name=current_task_name,
                current_assignment_id=current_assignment_id,
                progress_percent=progress_percent,
                current_step_title=current_step_title,
                current_step_number=current_step_num,
                total_steps=total_steps,
                interaction_mode=interaction_mode,
                interaction_health=interaction_health,
                active_session_id=active_session["id"] if active_session else None,
                session_duration_seconds=session_duration,
                has_open_assistance=has_open_assistance,
                is_emergency_stop=is_emergency,
                last_activity_at=user.get("updated_at") or user.get("created_at"),
            )
            result.append(item)

        return result

    def get_worker_detail(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
    ) -> SupervisorWorkerDetail:
        """
        Get deep-dive inspection detail for a specific worker.
        Validates organization tenancy.
        """
        worker_profile = self.worker_profiles_repo.get_by_id(worker_profile_id)
        if not worker_profile:
            raise NotFoundError(f"Worker profile {worker_profile_id} not found.")

        user = self.users_repo.get_by_id(worker_profile["user_id"])
        if not user or user.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Worker does not belong to your organization.")

        # Find general worker item
        workers = self.list_organization_workers(organization_id)
        base_item = next((w for w in workers if w.worker_profile_id == worker_profile_id), None)
        if not base_item:
            raise NotFoundError(f"Worker {worker_profile_id} telemetry not found.")

        # Step details derived from real workflow step executions
        step_details: List[Dict[str, Any]] = []
        if base_item.current_assignment_id and base_item.current_task_id:
            progress = self._worker_workflow_progress(worker_profile_id, base_item.current_task_id)
            if progress:
                for idx, step in enumerate(progress["steps"], 1):
                    is_done = step["id"] in progress["completed_ids"]
                    is_current = (
                        progress["current_step"] is not None
                        and step["id"] == progress["current_step"]["id"]
                    )
                    if is_done:
                        st = "completed"
                    elif is_current:
                        st = "in_progress"
                    else:
                        st = "pending"
                    step_details.append({
                        "step_number": idx,
                        "title": step.get("name") or step.get("title") or f"Step {idx}",
                        "description": step.get("description"),
                        "status": st,
                        "is_current": is_current,
                    })

        # Recent assistance history
        raw_reqs = self.assistance_requests_repo.list_by_worker_profile_id(worker_profile_id)
        recent_assistance = [
            {
                "id": str(r["id"]),
                "reason": r.get("reason"),
                "status": r.get("status"),
                "priority": r.get("priority"),
                "requested_at": str(r.get("requested_at")),
                "resolved_at": str(r.get("resolved_at")) if r.get("resolved_at") else None,
            }
            for r in raw_reqs[-10:]
        ]

        # Recent task assignments (with recorded outcome for completed work)
        raw_assigns = self.worker_task_assignments_repo.list_by_worker_profile_id(worker_profile_id)
        recent_tasks = []
        for a in raw_assigns[-10:]:
            t = self.tasks_repo.get_by_id(a["task_id"])
            outcome = None
            if a.get("status") in ("completed", "cancelled"):
                result = self.task_results_repo.get_by_worker_task_assignment_id(a["id"])
                if result:
                    outcome = result.get("outcome")
            recent_tasks.append({
                "assignment_id": str(a["id"]),
                "task_id": str(a["task_id"]),
                "task_name": t.get("name") if t else None,
                "status": a.get("status"),
                "outcome": outcome,
                "assigned_at": str(a.get("assigned_at")),
                "completed_at": str(a.get("completed_at")) if a.get("completed_at") else None,
            })

        return SupervisorWorkerDetail(
            **base_item.model_dump(),
            step_details=step_details,
            recent_assistance_requests=recent_assistance,
            recent_task_assignments=recent_tasks,
        )

    def list_assignable_tasks(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """List active assignable tasks for the supervisor's organization."""
        all_tasks = self.tasks_repo.list_by_organization_id(organization_id) if hasattr(self.tasks_repo, "list_by_organization_id") else []
        return [
            {
                "id": t["id"],
                "name": t.get("name"),
                "description": t.get("description"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
            }
            for t in all_tasks
            if t.get("status") == "active"
        ]

    def assign_task(
        self,
        organization_id: UUID,
        supervisor_user_id: UUID,
        payload: TaskAssignmentPayload,
    ) -> Dict[str, Any]:
        """
        Assign an active task to an eligible worker in the same organization.
        Enforces tenant isolation and logs to the immutable audit timeline.
        """
        # 1. Validate task
        task = self.tasks_repo.get_by_id(payload.task_id)
        if not task:
            raise NotFoundError(f"Task {payload.task_id} not found.")
        if task.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Task belongs to another organization.")
        if task.get("status") != "active":
            raise ConflictError(f"Task is in '{task.get('status')}' status and cannot be assigned.")

        # 2. Validate worker
        worker_profile = self.worker_profiles_repo.get_by_id(payload.worker_profile_id)
        if not worker_profile:
            raise NotFoundError(f"Worker profile {payload.worker_profile_id} not found.")
        worker_user = self.users_repo.get_by_id(worker_profile["user_id"])
        if not worker_user or worker_user.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Worker belongs to another organization.")

        # 3. Create task assignment
        assignment = self.worker_task_assignments_repo.create(
            task_id=payload.task_id,
            worker_profile_id=payload.worker_profile_id,
        )

        # 4. Log to Audit Timeline
        self.audit_events_repo.create(
            organization_id=organization_id,
            actor_user_id=supervisor_user_id,
            event_type="supervisor_task_assigned",
            resource_type="worker_task_assignment",
            resource_id=assignment["id"],
            event_data={
                "task_id": str(payload.task_id),
                "task_name": task.get("name"),
                "worker_profile_id": str(payload.worker_profile_id),
                "worker_name": worker_user.get("full_name") or worker_user["email"],
                "notes": payload.notes,
            },
        )

        return {
            "message": f"Task '{task.get('name')}' successfully assigned to {worker_user.get('full_name') or worker_user['email']}.",
            "assignment": assignment,
        }

    def reassign_task(
        self,
        organization_id: UUID,
        supervisor_user_id: UUID,
        assignment_id: UUID,
        payload: TaskReassignmentPayload,
    ) -> Dict[str, Any]:
        """
        Reassign an active task assignment to another worker within the same organization.
        """
        assignment = self.worker_task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        task = self.tasks_repo.get_by_id(assignment["task_id"])
        if not task or task.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Task belongs to another organization.")

        if assignment.get("status") in ("completed", "failed", "cancelled"):
            raise ConflictError(f"Cannot reassign task assignment in '{assignment.get('status')}' state.")

        new_worker = self.worker_profiles_repo.get_by_id(payload.new_worker_profile_id)
        if not new_worker:
            raise NotFoundError(f"Worker profile {payload.new_worker_profile_id} not found.")
        new_user = self.users_repo.get_by_id(new_worker["user_id"])
        if not new_user or new_user.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Target worker belongs to another organization.")

        # Update assignment to cancelled for previous, and create new
        self.worker_task_assignments_repo.update_status(
            worker_task_assignment_id=assignment_id,
            status="cancelled",
        ) if hasattr(self.worker_task_assignments_repo, "update_status") else None

        new_assignment = self.worker_task_assignments_repo.create(
            task_id=assignment["task_id"],
            worker_profile_id=payload.new_worker_profile_id,
        )

        self.audit_events_repo.create(
            organization_id=organization_id,
            actor_user_id=supervisor_user_id,
            event_type="supervisor_task_reassigned",
            resource_type="worker_task_assignment",
            resource_id=new_assignment["id"],
            event_data={
                "previous_assignment_id": str(assignment_id),
                "new_assignment_id": str(new_assignment["id"]),
                "task_id": str(assignment["task_id"]),
                "new_worker_profile_id": str(payload.new_worker_profile_id),
                "reason": payload.reason,
            },
        )

        return {
            "message": f"Task successfully reassigned to {new_user.get('full_name') or new_user['email']}.",
            "new_assignment": new_assignment,
        }

    def list_assistance_requests(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all assistance requests for the organization with worker, task, and emergency tags.
        """
        requests = self.assistance_requests_repo.list_by_organization_id(organization_id)
        result: List[Dict[str, Any]] = []

        for req in requests:
            if status and req.get("status") != status:
                continue
            if priority and req.get("priority") != priority:
                continue

            wp_id = req.get("worker_profile_id")
            worker_name = "Worker"
            worker_email = "worker@amap.com"

            if wp_id:
                wp = self.worker_profiles_repo.get_by_id(wp_id)
                if wp:
                    u = self.users_repo.get_by_id(wp["user_id"])
                    if u:
                        worker_name = u.get("full_name") or u["email"]
                        worker_email = u["email"]

            task_name = "Assembly Operation"
            wta_id = req.get("worker_task_assignment_id")
            if wta_id:
                wta = self.worker_task_assignments_repo.get_by_id(wta_id)
                if wta:
                    t = self.tasks_repo.get_by_id(wta["task_id"])
                    if t:
                        task_name = t.get("name") or task_name

            reason_str = req.get("reason") or ""
            is_emergency = req.get("priority") == "urgent" or "emergency" in reason_str.lower()

            result.append({
                "id": str(req["id"]),
                "organization_id": str(organization_id),
                "worker_profile_id": str(wp_id) if wp_id else None,
                "worker_name": worker_name,
                "worker_email": worker_email,
                "task_name": task_name,
                "status": req.get("status", "open"),
                "priority": req.get("priority", "normal"),
                "reason": reason_str or "Worker requested supervisor assistance",
                "request_data": req.get("request_data") or {},
                "is_emergency": is_emergency,
                "requested_at": req.get("requested_at"),
                "acknowledged_at": req.get("acknowledged_at"),
                "resolved_at": req.get("resolved_at"),
            })

        # Order by priority (urgent first) then requested_at desc
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        result.sort(
            key=lambda r: (
                0 if r["is_emergency"] else 1,
                priority_order.get(r["priority"], 99),
            )
        )
        return result

    def acknowledge_assistance(
        self,
        organization_id: UUID,
        supervisor_user_id: UUID,
        request_id: UUID,
    ) -> Dict[str, Any]:
        """Acknowledge an open assistance request."""
        req = self.assistance_requests_repo.get_by_id(request_id)
        if not req:
            raise NotFoundError(f"Assistance request {request_id} not found.")
        if req.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Assistance request belongs to another organization.")

        updated = self.assistance_requests_repo.update_status(
            assistance_request_id=request_id,
            status="acknowledged",
            acknowledged_at=datetime.now(timezone.utc),
        )

        self.audit_events_repo.create(
            organization_id=organization_id,
            actor_user_id=supervisor_user_id,
            event_type="supervisor_assistance_acknowledged",
            resource_type="assistance_request",
            resource_id=request_id,
            event_data={"status": "acknowledged"},
        )

        return {"message": "Assistance request acknowledged.", "request": updated}

    def respond_to_assistance(
        self,
        organization_id: UUID,
        supervisor_user_id: UUID,
        request_id: UUID,
        payload: AssistanceResponsePayload,
    ) -> Dict[str, Any]:
        """Send supervisor instructions/guidance to the worker."""
        req = self.assistance_requests_repo.get_by_id(request_id)
        if not req:
            raise NotFoundError(f"Assistance request {request_id} not found.")
        if req.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Assistance request belongs to another organization.")

        req_data = req.get("request_data") or {}
        req_data["supervisor_guidance"] = payload.guidance_message
        req_data["resolution_action"] = payload.resolution_action
        req_data["responded_by"] = str(supervisor_user_id)
        req_data["responded_at"] = datetime.now(timezone.utc).isoformat()

        updated = self.assistance_requests_repo.update_status(
            assistance_request_id=request_id,
            status="in_progress",
            request_data=req_data,
        )

        self.audit_events_repo.create(
            organization_id=organization_id,
            actor_user_id=supervisor_user_id,
            event_type="supervisor_assistance_responded",
            resource_type="assistance_request",
            resource_id=request_id,
            event_data={
                "guidance_message": payload.guidance_message,
                "resolution_action": payload.resolution_action,
            },
        )

        return {"message": "Supervisor guidance transmitted to worker.", "request": updated}

    def resolve_assistance(
        self,
        organization_id: UUID,
        supervisor_user_id: UUID,
        request_id: UUID,
        payload: Optional[AssistanceResolvePayload] = None,
    ) -> Dict[str, Any]:
        """Resolve and close an assistance request."""
        req = self.assistance_requests_repo.get_by_id(request_id)
        if not req:
            raise NotFoundError(f"Assistance request {request_id} not found.")
        if req.get("organization_id") != organization_id:
            raise UnauthorizedError("Access denied: Assistance request belongs to another organization.")

        req_data = req.get("request_data") or {}
        if payload and payload.resolution_notes:
            req_data["final_resolution_notes"] = payload.resolution_notes

        updated = self.assistance_requests_repo.update_status(
            assistance_request_id=request_id,
            status="resolved",
            resolved_at=datetime.now(timezone.utc),
            request_data=req_data,
        )

        self.audit_events_repo.create(
            organization_id=organization_id,
            actor_user_id=supervisor_user_id,
            event_type="supervisor_assistance_resolved",
            resource_type="assistance_request",
            resource_id=request_id,
            event_data={
                "status": "resolved",
                "notes": payload.resolution_notes if payload else None,
            },
        )

        return {"message": "Assistance request successfully resolved.", "request": updated}

    def list_emergency_events(self, organization_id: UUID) -> List[Dict[str, Any]]:
        """List active emergency stop events for the supervisor's organization."""
        requests = self.list_assistance_requests(organization_id)
        return [r for r in requests if r.get("is_emergency") and r.get("status") in ("open", "acknowledged", "in_progress")]

    def get_operational_analytics(self, organization_id: UUID) -> SupervisorAnalytics:
        """
        Aggregate actual operational metrics and assistance resolution data.
        Zero mock statistics.
        """
        all_tasks = self.tasks_repo.list_by_organization_id(organization_id) if hasattr(self.tasks_repo, "list_by_organization_id") else []
        assigned = 0
        completed = 0
        in_prog = 0
        durations: List[float] = []

        for task in all_tasks:
            assignments = self.worker_task_assignments_repo.list_by_task_id(task["id"])
            for a in assignments:
                assigned += 1
                st = a.get("status")
                if st == "completed":
                    completed += 1
                    if a.get("started_at") and a.get("completed_at"):
                        dur = (a["completed_at"] - a["started_at"]).total_seconds() / 60.0
                        durations.append(dur)
                elif st in ("in_progress", "assigned", "paused"):
                    in_prog += 1

        avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0
        completion_rate = round((completed / max(1, assigned)) * 100.0 if assigned > 0 else 0.0, 1)

        reqs = self.assistance_requests_repo.list_by_organization_id(organization_id)
        total_reqs = len(reqs)
        resolved_reqs = sum(1 for r in reqs if r.get("status") == "resolved")

        res_times: List[float] = []
        emergency_count = 0
        for r in reqs:
            if r.get("priority") == "urgent" or "emergency" in (r.get("reason") or "").lower():
                emergency_count += 1
            if r.get("requested_at") and r.get("resolved_at"):
                t = (r["resolved_at"] - r["requested_at"]).total_seconds() / 60.0
                res_times.append(t)

        avg_res_time = round(sum(res_times) / len(res_times), 1) if res_times else 0.0

        return SupervisorAnalytics(
            tasks_assigned_count=assigned,
            tasks_completed_count=completed,
            tasks_in_progress_count=in_prog,
            average_task_duration_minutes=avg_dur,
            workflow_completion_rate=completion_rate,
            total_assistance_requests=total_reqs,
            resolved_assistance_requests=resolved_reqs,
            average_resolution_time_minutes=avg_res_time,
            emergency_stops_count=emergency_count,
        )

    def list_audit_timeline(self, organization_id: UUID, limit: int = 50) -> List[SupervisorAuditEvent]:
        """List immutable audit events for the organization."""
        events = self.audit_events_repo.list_by_organization_id(organization_id)
        result: List[SupervisorAuditEvent] = []

        for e in events[:limit]:
            actor_name = "System"
            actor_email = None
            if e.get("actor_user_id"):
                u = self.users_repo.get_by_id(e["actor_user_id"])
                if u:
                    actor_name = u.get("full_name") or u["email"]
                    actor_email = u["email"]

            result.append(
                SupervisorAuditEvent(
                    id=e["id"],
                    event_type=e.get("event_type", "operation"),
                    actor_id=e.get("actor_user_id"),
                    actor_name=actor_name,
                    actor_email=actor_email,
                    resource_type=e.get("resource_type", "entity"),
                    resource_id=e.get("resource_id"),
                    event_data=e.get("event_data") or {},
                    occurred_at=e.get("occurred_at") or e.get("created_at") or datetime.now(timezone.utc),
                )
            )

        return result
