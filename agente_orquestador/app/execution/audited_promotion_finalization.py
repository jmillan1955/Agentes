from __future__ import annotations

from pathlib import Path

from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.execution.promotion_commit import (
    PromotionCommitError,
    PromotionCommitService,
)
from app.execution.promotion_preview import (
    PromotionPreviewError,
    PromotionPreviewService,
)
from app.execution.promotion_records import (
    PromotionStatus,
    TaskExecutionPromotion,
)
from app.execution.promotion_validation import (
    PromotionValidationError,
    PromotionValidationService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowError,
    PromotionWorkflowResult,
    PromotionWorkflowService,
)
from app.execution.sandbox import (
    SandboxRunResult,
)


class AuditedPromotionFinalizationError(
    RuntimeError
):
    """No se pudo finalizar la promocion auditada."""

    def __init__(
        self,
        message: str,
        sandbox_result: (
            SandboxRunResult | None
        ) = None,
    ) -> None:
        super().__init__(message)

        self.sandbox_result = sandbox_result


class AuditedPromotionFinalizationService:
    def __init__(
        self,
        promotion_repository: (
            TaskExecutionPromotionRepository
        ),
        preview_service: (
            PromotionPreviewService
        ),
        workflow_service: (
            PromotionWorkflowService
        ),
        validation_service: (
            PromotionValidationService
        ),
        commit_service: (
            PromotionCommitService
        ),
    ) -> None:
        self._promotion_repository = (
            promotion_repository
        )
        self._preview_service = (
            preview_service
        )
        self._workflow_service = (
            workflow_service
        )
        self._validation_service = (
            validation_service
        )
        self._commit_service = commit_service

    def finalize(
        self,
        promotion_id: int,
        confirmed_by_user_id: str,
        confirmation_message_id: str,
        confirmation_channel: str,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise (
                AuditedPromotionFinalizationError(
                    "promotion_id debe ser mayor "
                    "que cero"
                )
            )

        promotion = (
            self._promotion_repository
            .get_by_id(promotion_id)
        )

        if promotion is None:
            raise (
                AuditedPromotionFinalizationError(
                    "No existe la promocion"
                )
            )

        if (
            promotion.status
            == PromotionStatus.COMMITTED
        ):
            if (
                promotion.confirmed_by_user_id
                == confirmed_by_user_id.strip()
                and promotion
                .confirmation_message_id
                == confirmation_message_id.strip()
                and promotion
                .confirmation_channel
                == confirmation_channel.strip()
            ):
                return promotion

            raise (
                AuditedPromotionFinalizationError(
                    "La promocion ya fue "
                    "confirmada por otro mensaje "
                    "o usuario"
                )
            )

        if (
            promotion.status
            != PromotionStatus
            .PENDING_CONFIRMATION
        ):
            raise (
                AuditedPromotionFinalizationError(
                    "La promocion no esta "
                    "pendiente de confirmacion; "
                    "estado actual: "
                    f"{promotion.status.value}"
                )
            )

        try:
            preview = self._preview_service.create(
                workspace_path=Path(
                    promotion.workspace_path
                ),
                target_repository_root=Path(
                    promotion.repository_root
                ),
                target_subdirectory=(
                    promotion
                    .target_subdirectory
                ),
            )

        except PromotionPreviewError as error:
            self._record_failure(
                promotion_id=promotion.id,
                error_message=str(error),
                sandbox_result=None,
                rolled_back=False,
            )

            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo regenerar la "
                    f"vista previa: {error}"
                )
            ) from error

        if (
            preview.preview_hash
            != promotion.preview_hash
        ):
            error_message = (
                "El workspace o el repositorio "
                "cambiaron desde la vista previa"
            )

            self._record_failure(
                promotion_id=promotion.id,
                error_message=error_message,
                sandbox_result=None,
                rolled_back=False,
            )

            raise (
                AuditedPromotionFinalizationError(
                    error_message
                )
            )

        try:
            confirmed = (
                self._promotion_repository
                .confirm(
                    promotion_id=promotion.id,
                    confirmed_by_user_id=(
                        confirmed_by_user_id
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
            raise (
                AuditedPromotionFinalizationError(
                    str(error)
                )
            ) from error

        try:
            workflow_result = (
                self._workflow_service
                .apply_to_temporary_branch(
                    execution_id=(
                        confirmed.execution_id
                    ),
                    preview=preview,
                    confirmed_preview_hash=(
                        confirmed.preview_hash
                    ),
                )
            )

        except PromotionWorkflowError as error:
            self._record_failure(
                promotion_id=confirmed.id,
                error_message=str(error),
                sandbox_result=None,
                rolled_back=True,
            )

            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo aplicar la "
                    f"promocion: {error}"
                )
            ) from error

        try:
            applied = (
                self._promotion_repository
                .mark_applied(
                    promotion_id=confirmed.id,
                    promotion_branch=(
                        workflow_result
                        .branch
                        .promotion_branch
                    ),
                    base_commit=(
                        workflow_result
                        .branch
                        .base_commit
                    ),
                )
            )

        except Exception as error:
            self._rollback_after_audit_failure(
                promotion_id=confirmed.id,
                workflow_result=workflow_result,
                error_message=(
                    "No se pudo auditar la "
                    "aplicacion: "
                    f"{error}"
                ),
                sandbox_result=None,
            )

            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo registrar la "
                    "aplicacion de la promocion"
                )
            ) from error

        try:
            validation_result = (
                self._validation_service
                .validate(
                    workflow_result=(
                        workflow_result
                    ),
                    test_target=(
                        applied.test_target
                    ),
                )
            )

        except PromotionValidationError as error:
            self._record_failure(
                promotion_id=applied.id,
                error_message=str(error),
                sandbox_result=(
                    error.sandbox_result
                ),
                rolled_back=True,
            )

            raise (
                AuditedPromotionFinalizationError(
                    "La promocion no supero la "
                    f"validacion: {error}",
                    sandbox_result=(
                        error.sandbox_result
                    ),
                )
            ) from error

        try:
            validated = (
                self._promotion_repository
                .mark_validated(
                    promotion_id=applied.id,
                    sandbox_result=(
                        validation_result
                        .sandbox_result
                    ),
                )
            )

        except Exception as error:
            self._rollback_after_audit_failure(
                promotion_id=applied.id,
                workflow_result=workflow_result,
                error_message=(
                    "No se pudo auditar la "
                    "validacion: "
                    f"{error}"
                ),
                sandbox_result=(
                    validation_result
                    .sandbox_result
                ),
            )

            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo registrar la "
                    "validacion de la promocion",
                    sandbox_result=(
                        validation_result
                        .sandbox_result
                    ),
                )
            ) from error

        try:
            commit_result = (
                self._commit_service.commit(
                    execution_id=(
                        validated.execution_id
                    ),
                    validation=(
                        validation_result
                    ),
                )
            )

        except PromotionCommitError as error:
            try:
                self._workflow_service.rollback(
                    workflow_result
                )

            except PromotionWorkflowError as rollback_error:
                combined_error = (
                    "No se pudo crear el commit "
                    "y tampoco completar el "
                    "rollback: "
                    f"{rollback_error}"
                )

                self._record_failure(
                    promotion_id=validated.id,
                    error_message=(
                        combined_error
                    ),
                    sandbox_result=(
                        validation_result
                        .sandbox_result
                    ),
                    rolled_back=False,
                )

                raise (
                    AuditedPromotionFinalizationError(
                        combined_error,
                        sandbox_result=(
                            validation_result
                            .sandbox_result
                        ),
                    )
                ) from error

            self._record_failure(
                promotion_id=validated.id,
                error_message=str(error),
                sandbox_result=(
                    validation_result
                    .sandbox_result
                ),
                rolled_back=True,
            )

            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo crear el commit "
                    f"de promocion: {error}",
                    sandbox_result=(
                        validation_result
                        .sandbox_result
                    ),
                )
            ) from error

        try:
            return (
                self._promotion_repository
                .mark_committed(
                    promotion_id=validated.id,
                    commit_result=commit_result,
                )
            )

        except Exception as error:
            raise (
                AuditedPromotionFinalizationError(
                    "El commit fue creado, pero "
                    "no pudo registrarse en la "
                    f"auditoria: {error}",
                    sandbox_result=(
                        validation_result
                        .sandbox_result
                    ),
                )
            ) from error

    def _rollback_after_audit_failure(
        self,
        promotion_id: int,
        workflow_result: (
            PromotionWorkflowResult
        ),
        error_message: str,
        sandbox_result: (
            SandboxRunResult | None
        ),
    ) -> None:
        try:
            self._workflow_service.rollback(
                workflow_result
            )

        except PromotionWorkflowError as rollback_error:
            combined_error = (
                f"{error_message}. Ademas, no "
                "se pudo completar el rollback: "
                f"{rollback_error}"
            )

            self._record_failure(
                promotion_id=promotion_id,
                error_message=combined_error,
                sandbox_result=sandbox_result,
                rolled_back=False,
            )

            raise (
                AuditedPromotionFinalizationError(
                    combined_error,
                    sandbox_result=(
                        sandbox_result
                    ),
                )
            ) from rollback_error

        self._record_failure(
            promotion_id=promotion_id,
            error_message=error_message,
            sandbox_result=sandbox_result,
            rolled_back=True,
        )

    def _record_failure(
        self,
        promotion_id: int,
        error_message: str,
        sandbox_result: (
            SandboxRunResult | None
        ),
        rolled_back: bool,
    ) -> None:
        try:
            failed = (
                self._promotion_repository
                .mark_failed(
                    promotion_id=promotion_id,
                    error_message=(
                        error_message
                    ),
                    sandbox_result=(
                        sandbox_result
                    ),
                )
            )

            if rolled_back:
                (
                    self._promotion_repository
                    .mark_rolled_back(
                        promotion_id=failed.id
                    )
                )

        except Exception as audit_error:
            raise (
                AuditedPromotionFinalizationError(
                    "No se pudo conservar en la "
                    "auditoria el fallo de la "
                    f"promocion: {audit_error}",
                    sandbox_result=(
                        sandbox_result
                    ),
                )
            ) from audit_error