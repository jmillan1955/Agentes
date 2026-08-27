from __future__ import annotations

from dataclasses import dataclass

from app.context.task_execution_attempt_repository import (
    TaskExecutionAttemptRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.context.task_execution_step_repository import (
    TaskExecutionStepRepository,
)
from app.execution.models import (
    ExecutionAttempt,
    ExecutionStep,
    TaskExecution,
)


class ExecutionQueryError(
    ValueError
):
    """No se puede consultar la ejecucion."""


@dataclass(frozen=True, slots=True)
class ExecutionQueryResult:
    execution: TaskExecution
    attempts: tuple[
        ExecutionAttempt,
        ...,
    ]
    steps: tuple[
        ExecutionStep,
        ...,
    ]


class ExecutionQueryService:
    def __init__(
        self,
        execution_repository: (
            TaskExecutionRepository
        ),
        attempt_repository: (
            TaskExecutionAttemptRepository
        ),
        step_repository: (
            TaskExecutionStepRepository
        ),
    ) -> None:
        self._execution_repository = (
            execution_repository
        )
        self._attempt_repository = (
            attempt_repository
        )
        self._step_repository = (
            step_repository
        )

    def get_by_task_id(
        self,
        task_id: int,
    ) -> ExecutionQueryResult:
        if task_id <= 0:
            raise ExecutionQueryError(
                "El identificador de la tarea "
                "debe ser mayor que cero"
            )

        execution = (
            self._execution_repository
            .get_by_task_id(task_id)
        )

        if execution is None:
            raise ExecutionQueryError(
                "La tarea no tiene una "
                "ejecucion preparada"
            )

        attempts = (
            self._attempt_repository
            .list_by_execution(
                execution.id
            )
        )

        steps = tuple(
            step
            for attempt in attempts
            for step in (
                self._step_repository
                .list_by_attempt(attempt.id)
            )
        )

        return ExecutionQueryResult(
            execution=execution,
            attempts=attempts,
            steps=steps,
        )