from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.context.task_approval_repository import (
    TaskApprovalRepository,
)
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
    ExecutionManifestAction,
)
from app.execution.models import (
    ExecutionStatus,
    TaskExecution,
)


class ExecutionManifestConfirmationError(
    ValueError
):
    """No se puede revisar o confirmar."""


@dataclass(frozen=True, slots=True)
class ExecutionManifestReview:
    execution: TaskExecution
    manifest: ExecutionManifest
    actions: tuple[
        ExecutionManifestAction,
        ...,
    ]
    requires_extra_confirmation: bool


class ExecutionManifestService:
    def __init__(
        self,
        execution_repository: (
            TaskExecutionRepository
        ),
        approval_repository: (
            TaskApprovalRepository
        ),
        manifest_repository: (
            TaskExecutionManifestRepository
        ),
    ) -> None:
        self._execution_repository = (
            execution_repository
        )
        self._approval_repository = (
            approval_repository
        )
        self._manifest_repository = (
            manifest_repository
        )

    def create(
        self,
        execution_id: int,
        actions: Iterable[
            ExecutionAction
        ],
    ) -> ExecutionManifest:
        execution = (
            self._execution_repository
            .get_by_id(execution_id)
        )

        if execution is None:
            raise ExecutionManifestConfirmationError(
                "No existe la ejecucion"
            )

        if (
            execution.status
            != ExecutionStatus.PREPARED
        ):
            raise ExecutionManifestConfirmationError(
                "Solo se puede crear el "
                "manifiesto de una ejecucion "
                "preparada"
            )

        return self._manifest_repository.create(
            execution_id=execution.id,
            actions=actions,
        )

    def get_by_task_id(
        self,
        task_id: int,
    ) -> ExecutionManifestReview:
        if task_id <= 0:
            raise ExecutionManifestConfirmationError(
                "El identificador de la tarea "
                "debe ser mayor que cero"
            )

        execution = (
            self._execution_repository
            .get_by_task_id(task_id)
        )

        if execution is None:
            raise ExecutionManifestConfirmationError(
                "La tarea no tiene una "
                "ejecucion preparada"
            )

        manifest = (
            self._manifest_repository
            .get_latest(execution.id)
        )

        if manifest is None:
            raise ExecutionManifestConfirmationError(
                "La ejecucion no tiene un "
                "manifiesto de acciones"
            )

        actions = (
            self._manifest_repository
            .list_actions(manifest.id)
        )

        if len(actions) != manifest.action_count:
            raise RuntimeError(
                "El numero de acciones no "
                "coincide con el manifiesto"
            )

        return ExecutionManifestReview(
            execution=execution,
            manifest=manifest,
            actions=actions,
            requires_extra_confirmation=(
                manifest
                .requires_extra_confirmation
            ),
        )

    def confirm(
        self,
        task_id: int,
        expected_manifest_hash: str,
        confirmed_by_user_id: str,
        confirmation_message_id: str,
        confirmation_channel: str,
        destructive_acknowledged: bool,
    ) -> ExecutionManifest:
        review = self.get_by_task_id(
            task_id
        )

        if (
            review.execution.status
            != ExecutionStatus.PREPARED
        ):
            raise ExecutionManifestConfirmationError(
                "Solo puede confirmarse el "
                "manifiesto de una ejecucion "
                "preparada"
            )

        approval = (
            self._approval_repository
            .get_by_task_id(task_id)
        )

        if (
            approval is None
            or approval.id
            != review.execution.approval_id
        ):
            raise ExecutionManifestConfirmationError(
                "La ejecucion no conserva una "
                "autorizacion valida"
            )

        normalized_user_id = (
            confirmed_by_user_id.strip()
        )

        if (
            normalized_user_id
            != approval.authorized_user_id
        ):
            raise ExecutionManifestConfirmationError(
                "Solo el usuario que aprobo "
                "el plan puede confirmar "
                "el manifiesto"
            )

        if (
            review
            .requires_extra_confirmation
            and not destructive_acknowledged
        ):
            raise ExecutionManifestConfirmationError(
                "El manifiesto contiene acciones "
                "destructivas y requiere una "
                "confirmacion adicional"
            )

        try:
            return (
                self._manifest_repository
                .confirm(
                    manifest_id=(
                        review.manifest.id
                    ),
                    expected_manifest_hash=(
                        expected_manifest_hash
                    ),
                    confirmed_by_user_id=(
                        normalized_user_id
                    ),
                    confirmation_message_id=(
                        confirmation_message_id
                    ),
                    confirmation_channel=(
                        confirmation_channel
                    ),
                )
            )

        except ValueError as error:
            raise ExecutionManifestConfirmationError(
                str(error)
            ) from error