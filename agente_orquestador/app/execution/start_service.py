from __future__ import annotations

from dataclasses import dataclass

from app.context.task_execution_manifest_repository import (
    TaskExecutionManifestRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.execution.actions import (
    ExecutionAction,
)
from app.execution.manifest_models import (
    ExecutionManifest,
    ExecutionManifestStatus,
)
from app.execution.models import (
    ExecutionStatus,
)
from app.execution.runner import (
    ExecutionRunner,
    ExecutionRunResult,
)


class ExecutionStartError(
    ValueError
):
    """La ejecucion no puede iniciarse."""


@dataclass(frozen=True, slots=True)
class ExecutionStartResult:
    manifest: ExecutionManifest
    actions: tuple[ExecutionAction, ...]
    run_result: ExecutionRunResult


class ExecutionStartService:
    def __init__(
        self,
        execution_repository: (
            TaskExecutionRepository
        ),
        manifest_repository: (
            TaskExecutionManifestRepository
        ),
        runner: ExecutionRunner,
    ) -> None:
        self._execution_repository = (
            execution_repository
        )
        self._manifest_repository = (
            manifest_repository
        )
        self._runner = runner

    def start(
        self,
        task_id: int,
        requested_by_user_id: str,
    ) -> ExecutionStartResult:
        return self._run(
            task_id=task_id,
            requested_by_user_id=(
                requested_by_user_id
            ),
            allowed_statuses=(
                ExecutionStatus.PREPARED,
            ),
            missing_execution_message=(
                "La tarea no tiene una "
                "ejecucion preparada"
            ),
            invalid_status_message=(
                "Solo puede iniciarse una "
                "ejecucion preparada"
            ),
        )

    def resume(
        self,
        task_id: int,
        requested_by_user_id: str,
    ) -> ExecutionStartResult:
        return self._run(
            task_id=task_id,
            requested_by_user_id=(
                requested_by_user_id
            ),
            allowed_statuses=(
                ExecutionStatus.FAILED,
                ExecutionStatus.INTERRUPTED,
            ),
            missing_execution_message=(
                "La tarea no tiene una "
                "ejecucion que reanudar"
            ),
            invalid_status_message=(
                "Solo puede reanudarse una "
                "ejecucion fallida o "
                "interrumpida"
            ),
        )

    def _run(
        self,
        task_id: int,
        requested_by_user_id: str,
        allowed_statuses: tuple[
            ExecutionStatus,
            ...,
        ],
        missing_execution_message: str,
        invalid_status_message: str,
    ) -> ExecutionStartResult:
        if task_id <= 0:
            raise ExecutionStartError(
                "El identificador de la tarea "
                "debe ser mayor que cero"
            )

        normalized_user_id = (
            requested_by_user_id.strip()
        )

        if not normalized_user_id:
            raise ExecutionStartError(
                "El usuario solicitante no puede "
                "estar vacio"
            )

        execution = (
            self._execution_repository
            .get_by_task_id(task_id)
        )

        if execution is None:
            raise ExecutionStartError(
                missing_execution_message
            )

        if (
            execution.status
            not in allowed_statuses
        ):
            raise ExecutionStartError(
                invalid_status_message
            )

        manifest = (
            self._manifest_repository
            .get_latest(execution.id)
        )

        if (
            manifest is None
            or manifest.status
            != ExecutionManifestStatus.CONFIRMED
        ):
            raise ExecutionStartError(
                "La ejecucion requiere un "
                "manifiesto confirmado"
            )

        if (
            manifest.execution_id
            != execution.id
        ):
            raise ExecutionStartError(
                "El manifiesto no pertenece a "
                "la ejecucion"
            )

        if (
            manifest.confirmed_by_user_id
            != normalized_user_id
        ):
            raise ExecutionStartError(
                "Solo el usuario que confirmo "
                "el manifiesto puede iniciar "
                "la ejecucion"
            )

        try:
            actions = (
                self._manifest_repository
                .load_confirmed_actions(
                    execution.id
                )
            )

        except (
            ValueError,
            RuntimeError,
        ) as error:
            raise ExecutionStartError(
                str(error)
            ) from error

        if not actions:
            raise ExecutionStartError(
                "El manifiesto confirmado no "
                "contiene acciones"
            )

        run_result = self._runner.run(
            execution_id=execution.id,
            actions=actions,
        )

        return ExecutionStartResult(
            manifest=manifest,
            actions=actions,
            run_result=run_result,
        )