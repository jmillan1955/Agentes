from __future__ import annotations

from dataclasses import dataclass

from app.execution.promotion_commit import (
    PromotionCommitError,
    PromotionCommitResult,
    PromotionCommitService,
)
from app.execution.promotion_models import (
    PromotionPreview,
)
from app.execution.promotion_validation import (
    PromotionValidationError,
    PromotionValidationResult,
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


class PromotionFinalizationError(
    RuntimeError
):
    """No se pudo finalizar la promocion."""

    def __init__(
        self,
        message: str,
        sandbox_result: (
            SandboxRunResult | None
        ) = None,
    ) -> None:
        super().__init__(message)

        self.sandbox_result = sandbox_result


@dataclass(frozen=True, slots=True)
class PromotionFinalizationResult:
    workflow: PromotionWorkflowResult
    validation: PromotionValidationResult
    commit: PromotionCommitResult


class PromotionFinalizationService:
    def __init__(
        self,
        workflow_service: (
            PromotionWorkflowService
        ),
        validation_service: (
            PromotionValidationService
        ),
        commit_service: PromotionCommitService,
    ) -> None:
        self._workflow_service = (
            workflow_service
        )
        self._validation_service = (
            validation_service
        )
        self._commit_service = commit_service

    def finalize(
        self,
        execution_id: int,
        preview: PromotionPreview,
        confirmed_preview_hash: str,
        test_target: str = ".",
    ) -> PromotionFinalizationResult:
        if execution_id <= 0:
            raise PromotionFinalizationError(
                "execution_id debe ser mayor "
                "que cero"
            )

        try:
            workflow_result = (
                self._workflow_service
                .apply_to_temporary_branch(
                    execution_id=execution_id,
                    preview=preview,
                    confirmed_preview_hash=(
                        confirmed_preview_hash
                    ),
                )
            )

        except PromotionWorkflowError as error:
            raise PromotionFinalizationError(
                "No se pudo aplicar la "
                f"promocion: {error}"
            ) from error

        try:
            validation_result = (
                self._validation_service
                .validate(
                    workflow_result=(
                        workflow_result
                    ),
                    test_target=test_target,
                )
            )

        except PromotionValidationError as error:
            raise PromotionFinalizationError(
                "La promocion no supero la "
                f"validacion: {error}",
                sandbox_result=(
                    error.sandbox_result
                ),
            ) from error

        try:
            commit_result = (
                self._commit_service.commit(
                    execution_id=execution_id,
                    validation=validation_result,
                )
            )

        except PromotionCommitError as error:
            try:
                self._workflow_service.rollback(
                    workflow_result
                )

            except PromotionWorkflowError as rollback_error:
                raise PromotionFinalizationError(
                    "La creacion del commit fallo "
                    "y tampoco se pudo completar "
                    "el rollback: "
                    f"{rollback_error}"
                ) from error

            raise PromotionFinalizationError(
                "No se pudo crear el commit de "
                f"promocion: {error}"
            ) from error

        return PromotionFinalizationResult(
            workflow=workflow_result,
            validation=validation_result,
            commit=commit_result,
        )