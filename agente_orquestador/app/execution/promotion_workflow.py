from __future__ import annotations

from dataclasses import dataclass

from app.execution.git_promotion import (
    GitPromotionBranch,
    GitPromotionBranchService,
    GitPromotionError,
)
from app.execution.promotion_application import (
    PromotionApplicationError,
    PromotionApplicationResult,
    PromotionApplicationService,
)
from app.execution.promotion_models import (
    PromotionPreview,
)
from pathlib import Path

class PromotionWorkflowError(
    RuntimeError
):
    """No se pudo completar el flujo de promocion."""


@dataclass(frozen=True, slots=True)
class PromotionWorkflowResult:
    branch: GitPromotionBranch
    application: PromotionApplicationResult


class PromotionWorkflowService:
    def __init__(
        self,
        branch_service: (
            GitPromotionBranchService
        ),
        application_service: (
            PromotionApplicationService
        ),
    ) -> None:
        self._branch_service = branch_service
        self._application_service = (
            application_service
        )

    def apply_to_temporary_branch(
        self,
        execution_id: int,
        preview: PromotionPreview,
        confirmed_preview_hash: str,
    ) -> PromotionWorkflowResult:
        if execution_id <= 0:
            raise PromotionWorkflowError(
                "execution_id debe ser mayor "
                "que cero"
            )

        branch_name = (
            "promotion/"
            f"execution-{execution_id}-"
            f"{preview.preview_hash[:12]}"
        )

        try:
            branch = self._branch_service.create(
                repository_root=Path(
                    preview
                    .target_repository_root
                ),
                branch_name=branch_name,
            )
        except GitPromotionError as error:
            raise PromotionWorkflowError(
                str(error)
            ) from error

        try:
            application = (
                self._application_service.apply(
                    preview=preview,
                    confirmed_preview_hash=(
                        confirmed_preview_hash
                    ),
                )
            )

        except PromotionApplicationError as error:
            try:
                self._branch_service.rollback(
                    branch
                )

            except GitPromotionError as rollback_error:
                raise PromotionWorkflowError(
                    "La promocion fallo y no se "
                    "pudo eliminar la rama "
                    "temporal: "
                    f"{rollback_error}"
                ) from error

            raise PromotionWorkflowError(
                str(error)
            ) from error

        return PromotionWorkflowResult(
            branch=branch,
            application=application,
        )