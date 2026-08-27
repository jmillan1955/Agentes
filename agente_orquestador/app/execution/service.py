from __future__ import annotations

from dataclasses import dataclass

from app.context.task_approval_repository import (
    TaskApprovalRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.context.task_repository import (
    TaskRepository,
)
from app.execution.models import TaskExecution
from app.execution.workspace import (
    WorkspacePolicy,
)


class ExecutionPreparationError(
    ValueError
):
    """No se puede preparar la ejecucion."""


@dataclass(frozen=True, slots=True)
class ExecutionPreparationResult:
    execution: TaskExecution
    already_prepared: bool


class ExecutionPreparationService:
    def __init__(
        self,
        task_repository: TaskRepository,
        approval_repository: (
            TaskApprovalRepository
        ),
        execution_repository: (
            TaskExecutionRepository
        ),
        workspace_policy: WorkspacePolicy,
    ) -> None:
        self._task_repository = (
            task_repository
        )
        self._approval_repository = (
            approval_repository
        )
        self._execution_repository = (
            execution_repository
        )
        self._workspace_policy = (
            workspace_policy
        )

    def prepare(
        self,
        task_id: int,
        requested_by_user_id: str,
        request_message_id: str,
        channel: str,
    ) -> ExecutionPreparationResult:
        if task_id <= 0:
            raise ExecutionPreparationError(
                "El identificador de la tarea "
                "debe ser mayor que cero"
            )

        task = self._task_repository.get_by_id(
            task_id
        )

        if task is None:
            raise ExecutionPreparationError(
                "No existe la tarea indicada"
            )

        if not task.target_project_name:
            raise ExecutionPreparationError(
                "La tarea no tiene un proyecto "
                "objetivo definido"
            )

        approval = (
            self._approval_repository
            .get_by_task_id(task_id)
        )

        if approval is None:
            raise ExecutionPreparationError(
                "La tarea no tiene una "
                "autorizacion aprobada"
            )

        workspace = (
            self._workspace_policy.resolve(
                task.target_project_name
            )
        )

        existing = (
            self._execution_repository
            .get_by_task_id(task_id)
        )

        try:
            execution = (
                self._execution_repository
                .prepare(
                    task_id=task.id,
                    plan_id=approval.plan_id,
                    approval_id=approval.id,
                    workspace_path=str(
                        workspace
                    ),
                    requested_by_user_id=(
                        requested_by_user_id
                    ),
                    request_message_id=(
                        request_message_id
                    ),
                    channel=channel,
                )
            )

        except ValueError as error:
            raise ExecutionPreparationError(
                str(error)
            ) from error

        return ExecutionPreparationResult(
            execution=execution,
            already_prepared=(
                existing is not None
            ),
        )