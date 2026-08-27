import pytest

from app.execution.models import (
    ExecutionAttempt,
    ExecutionAttemptStatus,
)


def create_attempt(
    status: ExecutionAttemptStatus = (
        ExecutionAttemptStatus.RUNNING
    ),
) -> ExecutionAttempt:
    return ExecutionAttempt(
        id=1,
        execution_id=2,
        attempt_number=1,
        status=status,
        started_at=(
            "2026-08-27T07:00:00.000Z"
        ),
        finished_at=None,
        exit_code=None,
        error_message=None,
    )


def test_creates_running_attempt() -> None:
    attempt = create_attempt()

    assert attempt.id == 1
    assert attempt.execution_id == 2
    assert attempt.attempt_number == 1
    assert (
        attempt.status
        == ExecutionAttemptStatus.RUNNING
    )
    assert attempt.is_terminal is False


@pytest.mark.parametrize(
    "status",
    (
        ExecutionAttemptStatus.COMPLETED,
        ExecutionAttemptStatus.FAILED,
        ExecutionAttemptStatus.INTERRUPTED,
        ExecutionAttemptStatus.CANCELLED,
    ),
)
def test_identifies_terminal_attempt(
    status: ExecutionAttemptStatus,
) -> None:
    attempt = create_attempt(
        status=status
    )

    assert attempt.is_terminal is True


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("id", 0),
        ("execution_id", 0),
        ("attempt_number", 0),
    ),
)
def test_rejects_invalid_identifier(
    field_name: str,
    invalid_value: int,
) -> None:
    values = {
        "id": 1,
        "execution_id": 2,
        "attempt_number": 1,
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError):
        ExecutionAttempt(
            **values,
            status=(
                ExecutionAttemptStatus.RUNNING
            ),
            started_at=(
                "2026-08-27T07:00:00.000Z"
            ),
            finished_at=None,
            exit_code=None,
            error_message=None,
        )