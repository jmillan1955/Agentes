from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.execution.models import (
    ExecutionStatus,
)
from app.execution.promotion_models import (
    PromotionPreview,
)
from app.execution.promotion_preview import (
    PromotionPreviewError,
    PromotionPreviewService,
)
from app.execution.promotion_records import (
    TaskExecutionPromotion,
)


class PromotionPreparationError(
    RuntimeError
):
    """No se pudo preparar la promocion."""


@dataclass(frozen=True, slots=True)
class PromotionPreparationResult:
    promotion: TaskExecutionPromotion
    preview: PromotionPreview


class PromotionPreparationService:
    def __init__(
        self,
        execution_repository: (
            TaskExecutionRepository
        ),
        preview_service: (
            PromotionPreviewService
        ),
        promotion_repository: (
            TaskExecutionPromotionRepository
        ),
    ) -> None:
        self._execution_repository = (
            execution_repository
        )
        self._preview_service = (
            preview_service
        )
        self._promotion_repository = (
            promotion_repository
        )

    def prepare(
        self,
        execution_id: int,
        target_repository_root: Path,
        requested_by_user_id: str,
        request_message_id: str,
        channel: str,
        target_subdirectory: str = ".",
        test_target: str = ".",
    ) -> PromotionPreparationResult:
        if execution_id <= 0:
            raise PromotionPreparationError(
                "execution_id debe ser mayor "
                "que cero"
            )

        execution = (
            self._execution_repository
            .get_by_id(execution_id)
        )

        if execution is None:
            raise PromotionPreparationError(
                "No existe la ejecucion"
            )

        if (
            execution.status
            != ExecutionStatus.COMPLETED
        ):
            raise PromotionPreparationError(
                "Solo puede promocionarse una "
                "ejecucion completada"
            )

        workspace_path = Path(
            execution.workspace_path
        )

        try:
            preview = self._preview_service.create(
                workspace_path=workspace_path,
                target_repository_root=(
                    target_repository_root
                ),
                target_subdirectory=(
                    target_subdirectory
                ),
            )

            promotion = (
                self._promotion_repository
                .create_pending(
                    execution_id=execution.id,
                    preview=preview,
                    requested_by_user_id=(
                        requested_by_user_id
                    ),
                    request_message_id=(
                        request_message_id
                    ),
                    channel=channel,
                    test_target=test_target,
                )
            )

        except (
            PromotionPreviewError,
            ValueError,
        ) as error:
            raise PromotionPreparationError(
                str(error)
            ) from error

        return PromotionPreparationResult(
            promotion=promotion,
            preview=preview,
        )