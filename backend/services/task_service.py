"""
Task and Workflow execution service for AMAP.

Orchestrates worker task assignment lifecycle and workflow step progressions.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from models.task import TaskRead
from models.worker import WorkerTaskAssignmentRead
from repositories.tasks import TasksRepository
from repositories.task_results import TaskResultsRepository
from repositories.task_workflows import TaskWorkflowsRepository
from repositories.worker_task_assignments import WorkerTaskAssignmentsRepository
from repositories.workflow_assignments import WorkflowAssignmentsRepository
from repositories.workflow_step_executions import WorkflowStepExecutionsRepository
from repositories.workflow_steps import WorkflowStepsRepository
from repositories.workflows import WorkflowsRepository
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class TaskService:
    """Business logic for tasks and workflow execution."""

    def __init__(
        self,
        tasks_repo: Optional[TasksRepository] = None,
        task_assignments_repo: Optional[WorkerTaskAssignmentsRepository] = None,
        task_results_repo: Optional[TaskResultsRepository] = None,
        task_workflows_repo: Optional[TaskWorkflowsRepository] = None,
        workflows_repo: Optional[WorkflowsRepository] = None,
        workflow_steps_repo: Optional[WorkflowStepsRepository] = None,
        workflow_assignments_repo: Optional[WorkflowAssignmentsRepository] = None,
        step_executions_repo: Optional[WorkflowStepExecutionsRepository] = None,
    ) -> None:
        self.tasks_repo = tasks_repo or TasksRepository()
        self.task_assignments_repo = task_assignments_repo or WorkerTaskAssignmentsRepository()
        self.task_results_repo = task_results_repo or TaskResultsRepository()
        self.task_workflows_repo = task_workflows_repo or TaskWorkflowsRepository()
        self.workflows_repo = workflows_repo or WorkflowsRepository()
        self.workflow_steps_repo = workflow_steps_repo or WorkflowStepsRepository()
        self.workflow_assignments_repo = workflow_assignments_repo or WorkflowAssignmentsRepository()
        self.step_executions_repo = step_executions_repo or WorkflowStepExecutionsRepository()

    def get_worker_assignments(self, worker_profile_id: UUID) -> List[WorkerTaskAssignmentRead]:
        """Return all task assignments for a worker profile (strictly read-only)."""
        assignments = self.task_assignments_repo.list_by_worker_profile_id(worker_profile_id)
        wf_assignments = self.workflow_assignments_repo.list_by_worker_profile_id(worker_profile_id)
        wf_map = {wa["workflow_id"]: wa["id"] for wa in wf_assignments}

        result: List[WorkerTaskAssignmentRead] = []
        for a in assignments:
            item = dict(a)
            if not item.get("workflow_assignment_id"):
                tw_links = self.task_workflows_repo.list_by_task_id(item["task_id"])
                for link in tw_links:
                    wf_id = link.get("workflow_id")
                    if wf_id in wf_map:
                        item["workflow_assignment_id"] = wf_map[wf_id]
                        break
            result.append(WorkerTaskAssignmentRead.model_validate(item))
        return result

    def start_task_assignment(
        self,
        assignment_id: UUID,
        worker_profile_id: UUID,
    ) -> WorkerTaskAssignmentRead:
        """Start a task assignment and ensure linked workflow assignment is in progress."""
        assignment = self.task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Task assignment does not belong to this worker.")

        if assignment["status"] in ("completed", "cancelled", "archived"):
            raise ConflictError("Cannot start an already completed/archived task assignment.")

        now = datetime.now(timezone.utc)
        updated = dict(self.task_assignments_repo.update_status(
            worker_task_assignment_id=assignment_id,
            status="in_progress",
            started_at=assignment.get("started_at") or now,
            completed_at=None,
        ))

        # Legitimate write lifecycle: ensure an ACTIVE workflow assignment
        # exists for this task cycle. A completed/cancelled workflow
        # assignment belongs to a previous cycle and must NOT be re-animated.
        tw_links = self.task_workflows_repo.list_by_task_id(assignment["task_id"])
        if tw_links:
            target_wf_id = tw_links[0]["workflow_id"]
            wf_assignments = self.workflow_assignments_repo.list_by_worker_profile_id(worker_profile_id)
            existing_wf = next(
                (
                    wa for wa in wf_assignments
                    if wa["workflow_id"] == target_wf_id
                    and wa.get("status") in ("assigned", "in_progress", "paused")
                ),
                None,
            )
            if existing_wf:
                if existing_wf.get("status") != "in_progress":
                    self.workflow_assignments_repo.update_status(
                        assignment_id=existing_wf["id"],
                        status="in_progress",
                    )
                updated["workflow_assignment_id"] = existing_wf["id"]
            else:
                new_wf = self.workflow_assignments_repo.create(
                    workflow_id=target_wf_id,
                    worker_profile_id=worker_profile_id,
                    status="in_progress",
                )
                updated["workflow_assignment_id"] = new_wf["id"]

        return WorkerTaskAssignmentRead.model_validate(updated)

    def complete_task_assignment(
        self,
        assignment_id: UUID,
        worker_profile_id: UUID,
        outcome: str = "completed",
        result_data: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete or cancel a task assignment and record its authoritative outcome/result."""
        if outcome not in ("completed", "failed", "partial", "cancelled"):
            raise ValidationError(f"Invalid outcome '{outcome}'.")

        assignment = self.task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Task assignment does not belong to this worker.")

        if assignment.get("status") in ("completed", "cancelled"):
            raise ConflictError(f"Cannot complete an already {assignment['status']} task assignment.")

        # Resolve linked workflow steps and verify completion if outcome is 'completed'
        total_steps = 0
        completed_steps = 0
        tw_links = []
        if assignment.get("task_id"):
            tw_links = self.task_workflows_repo.list_by_task_id(assignment["task_id"])
        if tw_links:
            target_wf_id = tw_links[0]["workflow_id"]
            wf_steps = self.workflow_steps_repo.list_by_workflow_id(target_wf_id)
            total_steps = len(wf_steps)
            if total_steps > 0:
                wf_assignments = self.workflow_assignments_repo.list_by_worker_profile_id(worker_profile_id)
                # Count executions of the CURRENT cycle's active workflow
                # assignment only — a completed one belongs to a previous run.
                wf_assign = next(
                    (
                        wa for wa in wf_assignments
                        if wa["workflow_id"] == target_wf_id
                        and wa.get("status") in ("assigned", "in_progress", "paused")
                    ),
                    None,
                )
                if wf_assign:
                    execs = self.step_executions_repo.list_by_workflow_assignment_id(wf_assign["id"])
                    completed_step_ids = {
                        e["workflow_step_id"] for e in execs if e.get("status") == "completed"
                    }
                    completed_steps = len([s for s in wf_steps if s["id"] in completed_step_ids])

                if outcome == "completed" and completed_steps < total_steps:
                    raise ConflictError(
                        f"Cannot complete task assignment: only {completed_steps}/{total_steps} required steps are completed."
                    )

        # Server-computed statistics (FR-09 server-truth integrity)
        now = datetime.now(timezone.utc)
        computed_stats: Dict[str, Any] = {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "outcome": outcome,
        }
        if assignment.get("started_at"):
            st_time = assignment["started_at"]
            if isinstance(st_time, datetime):
                computed_stats["duration_seconds"] = round((now - st_time).total_seconds(), 1)

        # Server truth overrides or supplements client claims
        final_result_data = {**(result_data or {}), **computed_stats}

        # Record task result
        existing_result = self.task_results_repo.get_by_worker_task_assignment_id(assignment_id)
        if existing_result:
            result = self.task_results_repo.update(
                task_result_id=existing_result["id"],
                outcome=outcome,
                result_data=final_result_data,
                notes=notes,
            )
        else:
            result = self.task_results_repo.create(
                worker_task_assignment_id=assignment_id,
                outcome=outcome,
                result_data=final_result_data,
                notes=notes,
            )

        # MUST FIX #1: If outcome is cancelled, status must be cancelled (NOT completed)
        target_status = "cancelled" if outcome == "cancelled" else "completed"
        self.task_assignments_repo.update_status(
            worker_task_assignment_id=assignment_id,
            status=target_status,
            started_at=assignment.get("started_at") or now,
            completed_at=now,
        )

        # Synchronize linked workflow assignment lifecycle
        if tw_links:
            target_wf_id = tw_links[0]["workflow_id"]
            wf_assignments = self.workflow_assignments_repo.list_by_worker_profile_id(worker_profile_id)
            active_wf = next(
                (wa for wa in wf_assignments if wa["workflow_id"] == target_wf_id and wa.get("status") == "in_progress"),
                None,
            )
            if not active_wf:
                active_wf = next((wa for wa in wf_assignments if wa["workflow_id"] == target_wf_id), None)

            if active_wf and active_wf.get("status") not in ("completed", "cancelled"):
                wf_status = "cancelled" if outcome == "cancelled" else "completed"
                self.workflow_assignments_repo.update_status(
                    assignment_id=active_wf["id"],
                    status=wf_status,
                )

        return result

    def cancel_task_assignment(
        self,
        assignment_id: UUID,
        worker_profile_id: UUID,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an in-progress or assigned task assignment."""
        return self.complete_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=worker_profile_id,
            outcome="cancelled",
            notes=notes or "Worker cancelled assignment",
        )

    def get_task_result(
        self,
        assignment_id: UUID,
        worker_profile_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        is_supervisor: bool = False,
    ) -> Dict[str, Any]:
        """Retrieve recorded task result with strict ownership & tenancy checks (FR-09)."""
        assignment = self.task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        # Tenancy check: verify task belongs to user's organization
        if organization_id:
            task = self.tasks_repo.get_by_id(assignment["task_id"])
            if task and task.get("organization_id") != organization_id:
                raise UnauthorizedError("Task assignment does not belong to user's organization.")

        # Worker ownership check: non-supervisors can only view their own assignment results
        if not is_supervisor and worker_profile_id:
            if assignment["worker_profile_id"] != worker_profile_id:
                raise UnauthorizedError("Task assignment does not belong to this worker.")

        result = self.task_results_repo.get_by_worker_task_assignment_id(assignment_id)
        if not result:
            raise NotFoundError(f"No task result recorded for assignment {assignment_id}.")

        return result

    def get_task_details(self, task_id: UUID, organization_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Return task details along with its ordered workflow steps, enforcing tenancy."""
        task = self.tasks_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found.")

        # MUST FIX #5: Organization Tenancy Boundary
        if organization_id and task.get("organization_id") != organization_id:
            raise UnauthorizedError("Task does not belong to user's organization.")

        tw_links = self.task_workflows_repo.list_by_task_id(task_id)
        workflow_id = tw_links[0]["workflow_id"] if tw_links else None
        steps: List[Dict[str, Any]] = []
        if workflow_id:
            raw_steps = self.workflow_steps_repo.list_by_workflow_id(workflow_id)
            steps = [
                {
                    "id": str(s["id"]),
                    "stepNumber": s.get("step_order", idx + 1),
                    "title": s.get("name") or s.get("title") or f"Step {idx + 1}",
                    "instructionText": s.get("description") or s.get("instruction") or "",
                    "isSafetyCritical": s.get("is_safety_critical", False),
                    "spatialTargetId": s.get("spatial_target_id") if "spatial_target_id" in s else None,
                }
                for idx, s in enumerate(raw_steps)
            ]

        return {
            "id": str(task["id"]),
            "organization_id": str(task["organization_id"]),
            "name": task.get("name", "Assembly Task"),
            "description": task.get("description"),
            "status": task.get("status", "active"),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "total_steps": len(steps),
            "steps": steps,
        }

    def get_step_executions(
        self,
        workflow_assignment_id: UUID,
        worker_profile_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Return the worker's own workflow step executions (completed + others)
        for an assignment so clients can restore persisted progress after a
        refresh or re-login. Enforces worker ownership of the assignment.
        """
        assignment = self.workflow_assignments_repo.get_by_id(workflow_assignment_id)
        if not assignment:
            raise NotFoundError(f"Workflow assignment {workflow_assignment_id} not found.")
        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Workflow assignment does not belong to this worker.")
        return self.step_executions_repo.list_by_workflow_assignment_id(workflow_assignment_id)

    def get_workflow_steps(self, workflow_id: UUID) -> List[Dict[str, Any]]:
        """Return ordered steps for a workflow."""
        workflow = self.workflows_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found.")

        return self.workflow_steps_repo.list_by_workflow_id(workflow_id)

    def record_step_execution(
        self,
        workflow_assignment_id: UUID,
        workflow_step_id: UUID,
        worker_profile_id: UUID,
        status: str = "in_progress",
        execution_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record or update the execution of a workflow step idempotently with order validation."""
        assignment = self.workflow_assignments_repo.get_by_id(workflow_assignment_id)
        if not assignment:
            raise NotFoundError(f"Workflow assignment {workflow_assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Workflow assignment does not belong to this worker.")

        # Terminal-state gate on the workflow assignment itself. Parent task
        # assignments are synchronized to terminal states together with the
        # workflow assignment on completion, so this check is authoritative
        # (a previous cycle's completed parent must not block a new cycle).
        if assignment.get("status") in ("completed", "cancelled"):
            raise ConflictError(
                f"Cannot record step execution on {assignment['status']} workflow assignment."
            )

        step = self.workflow_steps_repo.get_by_id(workflow_step_id)
        if not step or step["workflow_id"] != assignment["workflow_id"]:
            raise NotFoundError(f"Workflow step {workflow_step_id} is not part of this workflow.")

        existing = self.step_executions_repo.get_by_assignment_and_step(
            workflow_assignment_id=workflow_assignment_id,
            workflow_step_id=workflow_step_id,
        )

        # MUST FIX #4: Backend Step Order Enforcement
        # Preceding steps must be completed before a subsequent step can be executed
        current_order = step.get("step_order", 1)
        if current_order > 1 and not (existing and existing.get("status") == "completed"):
            all_steps = self.workflow_steps_repo.list_by_workflow_id(assignment["workflow_id"])
            preceding_steps = [s for s in all_steps if s.get("step_order", 1) < current_order]
            if preceding_steps:
                existing_execs = self.step_executions_repo.list_by_workflow_assignment_id(workflow_assignment_id)
                completed_step_ids = {
                    e["workflow_step_id"] for e in existing_execs if e.get("status") == "completed"
                }
                for p_step in preceding_steps:
                    if p_step["id"] not in completed_step_ids:
                        raise ConflictError(
                            f"Step order violation: preceding Step {p_step.get('step_order', 1)} "
                            f"('{p_step.get('name') or p_step.get('title')}') has not been completed."
                        )

        now = datetime.now(timezone.utc)
        notes_str = json.dumps(execution_data) if execution_data else None

        if existing:
            completed_at = now if status == "completed" else existing.get("completed_at")
            updated = self.step_executions_repo.update_status(
                execution_id=existing["id"],
                status=status,
                started_at=existing.get("started_at") or now,
                completed_at=completed_at,
                notes=notes_str or existing.get("notes"),
            )
            return updated or existing

        completed_at = now if status == "completed" else None
        execution = self.step_executions_repo.create(
            workflow_assignment_id=workflow_assignment_id,
            workflow_step_id=workflow_step_id,
            status=status,
            started_at=now,
            completed_at=completed_at,
            notes=notes_str,
        )
        return execution
