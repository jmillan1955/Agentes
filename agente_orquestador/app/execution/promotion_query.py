from __future__ import annotations

from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.execution.promotion_records import (
    TaskExecutionPromotion,
)


class PromotionQueryError(
    ValueError
):
    """No se puede consultar la promocion."""


class PromotionQueryService:
    def __init__(
        self,
        promotion_repository: (
            TaskExecutionPromotionRepository
        ),
    ) -> None:
        self._promotion_repository = (
            promotion_repository
        )

    def get_by_id(
        self,
        promotion_id: int,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise PromotionQueryError(
                "El identificador de la "
                "promocion debe ser mayor "
                "que cero"
            )

        promotion = (
            self._promotion_repository
            .get_by_id(promotion_id)
        )

        if promotion is None:
            raise PromotionQueryError(
                "No existe la promocion "
                f"#{promotion_id}"
            )

        return promotion