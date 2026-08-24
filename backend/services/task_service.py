"""
Task and Workflow execution service for AMAP.

Orchestrates worker task assignment lifecycle and workflow step progressions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from models.task import TaskRead
from models.worker import WorkerTaskAssignmentRead
from repositories.tasks import TasksRepository
from repositories.task_results import TaskResultsRepository
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
        workflows_repo: Optional[WorkflowsRepository] = None,
        workflow_steps_repo: Optional[WorkflowStepsRepository] = None,
        workflow_assignments_repo: Optional[WorkflowAssignmentsRepository] = None,
        step_executions_repo: Optional[WorkflowStepExecutionsRepository] = None,
    ) -> None:
        self.tasks_repo = tasks_repo or TasksRepository()
        self.task_assignments_repo = task_assignments_repo or WorkerTaskAssignmentsRepository()
        self.task_results_repo = task_results_repo or TaskResultsRepository()
        self.workflows_repo = workflows_repo or WorkflowsRepository()
        self.workflow_steps_repo = workflow_steps_repo or WorkflowStepsRepository()
        self.workflow_assignments_repo = workflow_assignments_repo or WorkflowAssignmentsRepository()
        self.step_executions_repo = step_executions_repo or WorkflowStepExecutionsRepository()

    def get_worker_assignments(self, worker_profile_id: UUID) -> List[WorkerTaskAssignmentRead]:
        """Return all task assignments for a worker profile."""
        assignments = self.task_assignments_repo.list_by_worker_profile_id(worker_profile_id)
        return [WorkerTaskAssignmentRead.model_validate(a) for a in assignments]

    def start_task_assignment(
        self,
        assignment_id: UUID,
        worker_profile_id: UUID,
    ) -> WorkerTaskAssignmentRead:
        """Start a task assignment."""
        assignment = self.task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Task assignment does not belong to this worker.")

        if assignment["status"] == "archived":
            raise ConflictError("Cannot start an already completed/archived task assignment.")

        now = datetime.now(timezone.utc)
        updated = self.task_assignments_repo.update_status(
            worker_task_assignment_id=assignment_id,
            status="active",
            started_at=assignment.get("started_at") or now,
            completed_at=None,
        )
        return WorkerTaskAssignmentRead.model_validate(updated)

    def complete_task_assignment(
        self,
        assignment_id: UUID,
        worker_profile_id: UUID,
        outcome: str = "completed",
        result_data: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete a task assignment and record its outcome/result."""
        if outcome not in ("completed", "failed", "partial", "cancelled"):
            raise ValidationError(f"Invalid outcome '{outcome}'.")

        assignment = self.task_assignments_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Task assignment {assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Task assignment does not belong to this worker.")

        # Record task result
        existing_result = self.task_results_repo.get_by_worker_task_assignment_id(assignment_id)
        if existing_result:
            result = self.task_results_repo.update(
                task_result_id=existing_result["id"],
                outcome=outcome,
                result_data=result_data or {},
                notes=notes,
            )
        else:
            result = self.task_results_repo.create(
                worker_task_assignment_id=assignment_id,
                outcome=outcome,
                result_data=result_data or {},
                notes=notes,
            )

        now = datetime.now(timezone.utc)
        self.task_assignments_repo.update_status(
            worker_task_assignment_id=assignment_id,
            status="archived",
            started_at=assignment.get("started_at") or now,
            completed_at=now,
        )

        return result

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
        """Record the execution of a workflow step."""
        assignment = self.workflow_assignments_repo.get_by_id(workflow_assignment_id)
        if not assignment:
            raise NotFoundError(f"Workflow assignment {workflow_assignment_id} not found.")

        if assignment["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Workflow assignment does not belong to this worker.")

        step = self.workflow_steps_repo.get_by_id(workflow_step_id)
        if not step or step["workflow_id"] != assignment["workflow_id"]:
            raise NotFoundError(f"Workflow step {workflow_step_id} is not part of this workflow.")

        execution = self.step_executions_repo.create(
            workflow_assignment_id=workflow_assignment_id,
            workflow_step_id=workflow_step_id,
            status=status,
            execution_data=execution_data or {},
        )
        return execution
