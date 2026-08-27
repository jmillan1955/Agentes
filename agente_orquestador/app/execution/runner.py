from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.context.task_execution_attempt_repository import (
    TaskExecutionAttemptRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.context.task_execution_step_repository import (
    TaskExecutionStepRepository,
)
from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.sandbox_executor import (
    SafeSandboxExecutor,
    SandboxActionExecutionError,
)
from app.execution.filesystem_executor import (
    SafeFilesystemExecutor,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.models import (
    ExecutionAttempt,
    ExecutionStatus,
    ExecutionStep,
    TaskExecution,
)


class ExecutionRunError(
    RuntimeError
):
    """La ejecucion controlada ha fallado."""


@dataclass(frozen=True, slots=True)
class ExecutionRunResult:
    execution: TaskExecution
    attempt: ExecutionAttempt
    steps: tuple[ExecutionStep, ...]


class ExecutionRunner:
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
        filesystem_executor: (
            SafeFilesystemExecutor
        ),
        limits: ExecutionLimits,
        sandbox_executor: (
            SafeSandboxExecutor | None
        ) = None,
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
        self._filesystem_executor = (
            filesystem_executor
        )
        self._limits = limits
        self._sandbox_executor = (
            sandbox_executor
        )

    def run(
        self,
        execution_id: int,
        actions: Iterable[ExecutionAction],
    ) -> ExecutionRunResult:
        action_values = tuple(actions)

        self._validate_actions(
            action_values
        )

        running = (
            self._execution_repository.start(
                execution_id
            )
        )

        attempt = (
            self._attempt_repository
            .get_current(running.id)
        )

        if attempt is None:
            raise ExecutionRunError(
                "No se ha creado el intento"
            )

        workspace = Path(
            running.workspace_path
        )

        for action in action_values:
            step = self._step_repository.create(
                attempt_id=attempt.id,
                step_number=(
                    action.step_number
                ),
                name=action.name,
                action_type=(
                    action.action_type.value
                ),
            )

            started_step = (
                self._step_repository.start(
                    step.id
                )
            )

            try:
                if (
                    action.action_type
                    == ExecutionActionType
                    .RUN_PYTEST
                ):
                    if (
                        self._sandbox_executor
                        is None
                    ):
                        raise ExecutionRunError(
                            "El backend de sandbox "
                            "no esta disponible"
                        )

                    sandbox_result = (
                        self._sandbox_executor
                        .execute(
                            workspace_path=workspace,
                            action=action,
                        )
                    )

                    stdout_text = (
                        sandbox_result.stdout_text
                    )
                    stderr_text = (
                        sandbox_result.stderr_text
                    )

                else:
                    filesystem_result = (
                        self._filesystem_executor
                        .execute(
                            workspace_path=workspace,
                            action=action,
                        )
                    )

                    stdout_text = (
                        filesystem_result.message
                    )
                    stderr_text = None

            except SandboxActionExecutionError as error:
                error_text = self._truncate(
                    str(error)
                )

                self._step_repository.fail(
                    step_id=started_step.id,
                    error_message=error_text,
                    exit_code=(
                        error.result.exit_code
                    ),
                    stdout_text=(
                        error.result.stdout_text
                    ),
                    stderr_text=(
                        error.result.stderr_text
                    ),
                )

                self._execution_repository.transition(
                    execution_id=running.id,
                    target_status=(
                        ExecutionStatus.FAILED
                    ),
                    last_error=error_text,
                )

                raise ExecutionRunError(
                    error_text
                ) from error

            except Exception as error:
                error_text = self._truncate(
                    str(error)
                    or type(error).__name__
                )

                self._step_repository.fail(
                    step_id=started_step.id,
                    error_message=error_text,
                )

                self._execution_repository.transition(
                    execution_id=running.id,
                    target_status=(
                        ExecutionStatus.FAILED
                    ),
                    last_error=error_text,
                )

                raise ExecutionRunError(
                    error_text
                ) from error

            self._step_repository.complete(
                step_id=started_step.id,
                stdout_text=self._truncate(
                    stdout_text
                ),
                stderr_text=self._truncate(
                    stderr_text
                )
                if stderr_text
                else None,
            )

        completed = (
            self._execution_repository.complete(
                running.id
            )
        )

        stored_steps = (
            self._step_repository
            .list_by_attempt(attempt.id)
        )

        return ExecutionRunResult(
            execution=completed,
            attempt=(
                self._attempt_repository
                .get_current(completed.id)
                or attempt
            ),
            steps=stored_steps,
        )

    def _validate_actions(
        self,
        actions: tuple[
            ExecutionAction,
            ...,
        ],
    ) -> None:
        if not actions:
            raise ExecutionRunError(
                "La ejecucion no contiene "
                "acciones"
            )

        if (
            len(actions)
            > self._limits.max_actions
        ):
            raise ExecutionRunError(
                "La ejecucion supera el numero "
                "maximo de acciones"
            )

        expected_numbers = tuple(
            range(1, len(actions) + 1)
        )
        actual_numbers = tuple(
            action.step_number
            for action in actions
        )

        if actual_numbers != expected_numbers:
            raise ExecutionRunError(
                "Las acciones deben estar "
                "ordenadas y numeradas desde 1"
            )

    def _truncate(
        self,
        text: str,
    ) -> str:
        limit = (
            self._limits
            .max_output_characters
        )

        if len(text) <= limit:
            return text

        return text[:limit]