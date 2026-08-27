import pytest

from app.execution.models import (
    ExecutionStepStatus,
)
from app.execution.state_machine import (
    ExecutionStepStateMachine,
    InvalidExecutionStepTransitionError,
)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    (
        (
            ExecutionStepStatus.PENDING,
            ExecutionStepStatus.RUNNING,
        ),
        (
            ExecutionStepStatus.PENDING,
            ExecutionStepStatus.SKIPPED,
        ),
        (
            ExecutionStepStatus.PENDING,
            ExecutionStepStatus.CANCELLED,
        ),
        (
            ExecutionStepStatus.RUNNING,
            ExecutionStepStatus.COMPLETED,
        ),
        (
            ExecutionStepStatus.RUNNING,
            ExecutionStepStatus.FAILED,
        ),
        (
            ExecutionStepStatus.RUNNING,
            ExecutionStepStatus.CANCELLED,
        ),
    ),
)
def test_allows_valid_step_transition(
    current_status: ExecutionStepStatus,
    target_status: ExecutionStepStatus,
) -> None:
    machine = ExecutionStepStateMachine()

    machine.validate_transition(
        current_status=current_status,
        target_status=target_status,
    )


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    (
        (
            ExecutionStepStatus.PENDING,
            ExecutionStepStatus.COMPLETED,
        ),
        (
            ExecutionStepStatus.COMPLETED,
            ExecutionStepStatus.RUNNING,
        ),
        (
            ExecutionStepStatus.FAILED,
            ExecutionStepStatus.RUNNING,
        ),
        (
            ExecutionStepStatus.SKIPPED,
            ExecutionStepStatus.RUNNING,
        ),
        (
            ExecutionStepStatus.CANCELLED,
            ExecutionStepStatus.RUNNING,
        ),
    ),
)
def test_rejects_invalid_step_transition(
    current_status: ExecutionStepStatus,
    target_status: ExecutionStepStatus,
) -> None:
    machine = ExecutionStepStateMachine()

    with pytest.raises(
        InvalidExecutionStepTransitionError
    ):
        machine.validate_transition(
            current_status=current_status,
            target_status=target_status,
        )