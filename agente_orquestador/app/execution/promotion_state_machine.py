from __future__ import annotations

from app.execution.promotion_records import (
    PromotionStatus,
)


class PromotionTransitionError(
    ValueError
):
    """La transicion de promocion no es valida."""


class PromotionStateMachine:
    _TRANSITIONS = {
        PromotionStatus.PENDING_CONFIRMATION: {
            PromotionStatus.CONFIRMED,
            PromotionStatus.FAILED,
        },
        PromotionStatus.CONFIRMED: {
            PromotionStatus.APPLIED,
            PromotionStatus.FAILED,
            PromotionStatus.ROLLED_BACK,
        },
        PromotionStatus.APPLIED: {
            PromotionStatus.VALIDATED,
            PromotionStatus.FAILED,
            PromotionStatus.ROLLED_BACK,
        },
        PromotionStatus.VALIDATED: {
            PromotionStatus.COMMITTED,
            PromotionStatus.FAILED,
            PromotionStatus.ROLLED_BACK,
        },
        PromotionStatus.COMMITTED: set(),
        PromotionStatus.FAILED: {
            PromotionStatus.ROLLED_BACK,
        },
        PromotionStatus.ROLLED_BACK: set(),
    }

    def validate_transition(
        self,
        current_status: PromotionStatus,
        target_status: PromotionStatus,
    ) -> None:
        if not isinstance(
            current_status,
            PromotionStatus,
        ):
            raise PromotionTransitionError(
                "El estado actual de la "
                "promocion no es valido"
            )

        if not isinstance(
            target_status,
            PromotionStatus,
        ):
            raise PromotionTransitionError(
                "El estado destino de la "
                "promocion no es valido"
            )

        allowed_targets = self._TRANSITIONS[
            current_status
        ]

        if target_status not in allowed_targets:
            raise PromotionTransitionError(
                "No se permite cambiar la "
                "promocion de "
                f"{current_status.value} a "
                f"{target_status.value}"
            )