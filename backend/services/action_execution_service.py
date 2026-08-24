"""
Deterministic action safety and execution service for AMAP.

Enforces the critical security boundary:
Recognition != Intent != Authorization != Execution

Every action execution must pass server-side safety checks and
prerequisite validation before mutating database state or executing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from models.action import ActionExecutionRequest, ActionExecutionResponse
from repositories.actions import ActionsRepository
from repositories.action_requirements import ActionRequirementsRepository
from repositories.execution_events import ExecutionEventsRepository
from repositories.task_actions import TaskActionsRepository
from repositories.workflow_step_actions import WorkflowStepActionsRepository
from services.base import NotFoundError, SafetyViolationError


class ActionExecutionService:
    """Business logic for deterministic action execution and safety validation."""

    def __init__(
        self,
        actions_repo: Optional[ActionsRepository] = None,
        action_requirements_repo: Optional[ActionRequirementsRepository] = None,
        workflow_step_actions_repo: Optional[WorkflowStepActionsRepository] = None,
        task_actions_repo: Optional[TaskActionsRepository] = None,
        execution_events_repo: Optional[ExecutionEventsRepository] = None,
    ) -> None:
        self.actions_repo = actions_repo or ActionsRepository()
        self.action_requirements_repo = action_requirements_repo or ActionRequirementsRepository()
        self.workflow_step_actions_repo = (
            workflow_step_actions_repo or WorkflowStepActionsRepository()
        )
        self.task_actions_repo = task_actions_repo or TaskActionsRepository()
        self.execution_events_repo = execution_events_repo or ExecutionEventsRepository()

    def validate_action_safety(
        self,
        action_name: str,
        workflow_step_id: Optional[UUID] = None,
        task_id: Optional[UUID] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate that the requested action is registered, active, compliant with
        all safety requirements, and permissible in the current workflow/task context.
        """
        action = self.actions_repo.get_by_name(action_name)
        if not action:
            raise NotFoundError(f"Action '{action_name}' is not registered.")

        if action["status"] != "active":
            raise SafetyViolationError(f"Action '{action_name}' is currently {action['status']}.")

        action_id = action["id"]

        # Check action requirements
        requirements = self.action_requirements_repo.list_by_action_id(action_id)
        for req in requirements:
            if req.get("status") == "active":
                req_type = req.get("requirement_type")
                req_data = req.get("requirement_data") or {}

                # Check parameter presence if required
                if req_type == "required_parameters":
                    required_keys = req_data.get("keys", [])
                    params = parameters or {}
                    missing = [k for k in required_keys if k not in params]
                    if missing:
                        raise SafetyViolationError(
                            f"Action '{action_name}' is missing required parameters: {missing}"
                        )

        # Context-specific validation: workflow step
        if workflow_step_id:
            step_link = self.workflow_step_actions_repo.get_by_ids(
                workflow_step_id=workflow_step_id,
                action_id=action_id,
            )
            if not step_link:
                # If step has specific actions linked, ensure this action is permitted
                all_step_actions = self.workflow_step_actions_repo.list_by_workflow_step_id(
                    workflow_step_id
                )
                if all_step_actions:
                    raise SafetyViolationError(
                        f"Action '{action_name}' is not permitted for workflow step {workflow_step_id}."
                    )

        # Context-specific validation: task
        if task_id:
            task_link = self.task_actions_repo.get_by_ids(
                task_id=task_id,
                action_id=action_id,
            )
            if not task_link:
                all_task_actions = self.task_actions_repo.list_by_task_id(task_id)
                if all_task_actions:
                    raise SafetyViolationError(
                        f"Action '{action_name}' is not permitted for task {task_id}."
                    )

        return action

    def execute_action(
        self,
        request: ActionExecutionRequest,
        worker_profile_id: UUID,
        organization_id: UUID,
    ) -> ActionExecutionResponse:
        """
        Validate safety and execute a deterministic action.
        Records an execution event for auditability.
        """
        # 1. Deterministic safety check
        action = self.validate_action_safety(
            action_name=request.action_name,
            workflow_step_id=request.workflow_step_id,
            task_id=request.task_id,
            parameters=request.parameters,
        )

        now = datetime.now(timezone.utc)

        # 2. Record execution event
        event_payload = {
            "action_id": str(action["id"]),
            "action_name": action["name"],
            "parameters": request.parameters,
            "work_session_id": str(request.work_session_id) if request.work_session_id else None,
            "workflow_step_id": str(request.workflow_step_id) if request.workflow_step_id else None,
            "task_id": str(request.task_id) if request.task_id else None,
        }

        self.execution_events_repo.create(
            organization_id=organization_id,
            event_type=f"action.{action['name']}.executed",
            worker_profile_id=worker_profile_id,
            event_data=event_payload,
        )

        # 3. Formulate feedback
        feedback = f"Action '{action['display_name']}' executed successfully."

        return ActionExecutionResponse(
            success=True,
            action_id=action["id"],
            action_name=action["name"],
            executed_at=now,
            result_data={"status": "executed", "parameters": request.parameters},
            feedback_message=feedback,
        )
