import pytest

from app.execution.models import (
    ExecutionStatus,
)
from app.execution.state_machine import (
    ExecutionStateMachine,
    InvalidExecutionTransitionError,
)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    (
        (
            ExecutionStatus.PREPARED,
            ExecutionStatus.RUNNING,
        ),
        (
            ExecutionStatus.PREPARED,
            ExecutionStatus.CANCELLED,
        ),
        (
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
        ),
        (
            ExecutionStatus.RUNNING,
            ExecutionStatus.FAILED,
        ),
        (
            ExecutionStatus.RUNNING,
            ExecutionStatus.INTERRUPTED,
        ),
        (
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
        ),
        (
            ExecutionStatus.FAILED,
            ExecutionStatus.RUNNING,
        ),
        (
            ExecutionStatus.INTERRUPTED,
            ExecutionStatus.RUNNING,
        ),
    ),
)
def test_allows_valid_transition(
    current_status: ExecutionStatus,
    target_status: ExecutionStatus,
) -> None:
    machine = ExecutionStateMachine()

    assert machine.can_transition(
        current_status=current_status,
        target_status=target_status,
    )

    machine.validate_transition(
        current_status=current_status,
        target_status=target_status,
    )


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    (
        (
            ExecutionStatus.PREPARED,
            ExecutionStatus.COMPLETED,
        ),
        (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.RUNNING,
        ),
        (
            ExecutionStatus.CANCELLED,
            ExecutionStatus.RUNNING,
        ),
        (
            ExecutionStatus.RUNNING,
            ExecutionStatus.PREPARED,
        ),
    ),
)
def test_rejects_invalid_transition(
    current_status: ExecutionStatus,
    target_status: ExecutionStatus,
) -> None:
    machine = ExecutionStateMachine()

    assert not machine.can_transition(
        current_status=current_status,
        target_status=target_status,
    )

    with pytest.raises(
        InvalidExecutionTransitionError
    ):
        machine.validate_transition(
            current_status=current_status,
            target_status=target_status,
        )


def test_returns_sorted_allowed_targets() -> None:
    machine = ExecutionStateMachine()

    assert machine.allowed_targets(
        ExecutionStatus.PREPARED
    ) == (
        ExecutionStatus.CANCELLED,
        ExecutionStatus.RUNNING,
    )


@pytest.mark.parametrize(
    "terminal_status",
    (
        ExecutionStatus.COMPLETED,
        ExecutionStatus.CANCELLED,
    ),
)
def test_terminal_status_has_no_targets(
    terminal_status: ExecutionStatus,
) -> None:
    machine = ExecutionStateMachine()

    assert (
        machine.allowed_targets(
            terminal_status
        )
        == ()
    )