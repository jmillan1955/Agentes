import pytest

from app.tasks import (
    InvalidTaskTransitionError,
    TaskStateMachine,
    TaskStatus,
)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        (
            TaskStatus.PENDING_PLANNING,
            TaskStatus.PENDING_CLARIFICATION,
        ),
        (
            TaskStatus.PENDING_PLANNING,
            TaskStatus.PENDING_APPROVAL,
        ),
        (
            TaskStatus.PENDING_CLARIFICATION,
            TaskStatus.PENDING_PLANNING,
        ),
        (
            TaskStatus.PENDING_APPROVAL,
            TaskStatus.APPROVED,
        ),
        (
            TaskStatus.APPROVED,
            TaskStatus.IN_PROGRESS,
        ),
        (
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
        ),
        (
            TaskStatus.IN_PROGRESS,
            TaskStatus.FAILED,
        ),
        (
            TaskStatus.PENDING_APPROVAL,
            TaskStatus.PENDING_PLANNING,
        ),
    ],
)
def test_accepts_valid_transition(
    current_status: TaskStatus,
    target_status: TaskStatus,
) -> None:
    machine = TaskStateMachine()

    machine.validate_transition(
        current_status=current_status,
        target_status=target_status,
    )

    assert machine.can_transition(
        current_status=current_status,
        target_status=target_status,
    )


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        (
            TaskStatus.PENDING_PLANNING,
            TaskStatus.COMPLETED,
        ),
        (
            TaskStatus.PENDING_APPROVAL,
            TaskStatus.IN_PROGRESS,
        ),
        (
            TaskStatus.APPROVED,
            TaskStatus.COMPLETED,
        ),
        (
            TaskStatus.COMPLETED,
            TaskStatus.IN_PROGRESS,
        ),
        (
            TaskStatus.CANCELLED,
            TaskStatus.PENDING_PLANNING,
        ),
        (
            TaskStatus.FAILED,
            TaskStatus.PENDING_PLANNING,
        ),
    ],
)
def test_rejects_invalid_transition(
    current_status: TaskStatus,
    target_status: TaskStatus,
) -> None:
    machine = TaskStateMachine()

    with pytest.raises(
        InvalidTaskTransitionError,
        match="No se permite cambiar",
    ):
        machine.validate_transition(
            current_status=current_status,
            target_status=target_status,
        )


def test_returns_allowed_targets() -> None:
    targets = (
        TaskStateMachine()
        .allowed_targets(
            TaskStatus.PENDING_APPROVAL
        )
    )

    assert targets == (
        TaskStatus.APPROVED,
        TaskStatus.CANCELLED,
        TaskStatus.PENDING_PLANNING,
    )


@pytest.mark.parametrize(
    "terminal_status",
    [
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ],
)
def test_terminal_status_has_no_targets(
    terminal_status: TaskStatus,
) -> None:
    targets = (
        TaskStateMachine()
        .allowed_targets(
            terminal_status
        )
    )

    assert targets == ()