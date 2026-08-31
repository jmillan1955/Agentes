import pytest

from app.execution.promotion_records import (
    PromotionStatus,
)
from app.execution.promotion_state_machine import (
    PromotionStateMachine,
    PromotionTransitionError,
)


@pytest.mark.parametrize(
    (
        "current_status",
        "target_status",
    ),
    (
        (
            PromotionStatus
            .PENDING_CONFIRMATION,
            PromotionStatus.CONFIRMED,
        ),
        (
            PromotionStatus
            .PENDING_CONFIRMATION,
            PromotionStatus.FAILED,
        ),
        (
            PromotionStatus.CONFIRMED,
            PromotionStatus.APPLIED,
        ),
        (
            PromotionStatus.CONFIRMED,
            PromotionStatus.FAILED,
        ),
        (
            PromotionStatus.CONFIRMED,
            PromotionStatus.ROLLED_BACK,
        ),
        (
            PromotionStatus.APPLIED,
            PromotionStatus.VALIDATED,
        ),
        (
            PromotionStatus.APPLIED,
            PromotionStatus.FAILED,
        ),
        (
            PromotionStatus.APPLIED,
            PromotionStatus.ROLLED_BACK,
        ),
        (
            PromotionStatus.VALIDATED,
            PromotionStatus.COMMITTED,
        ),
        (
            PromotionStatus.VALIDATED,
            PromotionStatus.FAILED,
        ),
        (
            PromotionStatus.VALIDATED,
            PromotionStatus.ROLLED_BACK,
        ),
        (
            PromotionStatus.FAILED,
            PromotionStatus.ROLLED_BACK,
        ),
    ),
)
def test_accepts_allowed_transition(
    current_status: PromotionStatus,
    target_status: PromotionStatus,
) -> None:
    PromotionStateMachine().validate_transition(
        current_status=current_status,
        target_status=target_status,
    )


@pytest.mark.parametrize(
    (
        "current_status",
        "target_status",
    ),
    (
        (
            PromotionStatus
            .PENDING_CONFIRMATION,
            PromotionStatus.APPLIED,
        ),
        (
            PromotionStatus
            .PENDING_CONFIRMATION,
            PromotionStatus.COMMITTED,
        ),
        (
            PromotionStatus.CONFIRMED,
            PromotionStatus.COMMITTED,
        ),
        (
            PromotionStatus.APPLIED,
            PromotionStatus.COMMITTED,
        ),
        (
            PromotionStatus.COMMITTED,
            PromotionStatus.ROLLED_BACK,
        ),
        (
            PromotionStatus.ROLLED_BACK,
            PromotionStatus.CONFIRMED,
        ),
        (
            PromotionStatus.FAILED,
            PromotionStatus.COMMITTED,
        ),
        (
            PromotionStatus.CONFIRMED,
            PromotionStatus.CONFIRMED,
        ),
    ),
)
def test_rejects_forbidden_transition(
    current_status: PromotionStatus,
    target_status: PromotionStatus,
) -> None:
    with pytest.raises(
        PromotionTransitionError,
        match="No se permite",
    ):
        (
            PromotionStateMachine()
            .validate_transition(
                current_status=(
                    current_status
                ),
                target_status=target_status,
            )
        )