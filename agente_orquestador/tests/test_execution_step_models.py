import pytest

from app.execution.models import (
    ExecutionStep,
    ExecutionStepStatus,
)


def create_step(
    status: ExecutionStepStatus = (
        ExecutionStepStatus.PENDING
    ),
) -> ExecutionStep:
    return ExecutionStep(
        id=1,
        attempt_id=2,
        step_number=1,
        name="Crear estructura",
        action_type="filesystem",
        status=status,
        started_at=None,
        finished_at=None,
        exit_code=None,
        stdout_text=None,
        stderr_text=None,
        error_message=None,
    )


def test_creates_pending_step() -> None:
    step = create_step()

    assert step.id == 1
    assert step.attempt_id == 2
    assert step.step_number == 1
    assert (
        step.status
        == ExecutionStepStatus.PENDING
    )
    assert step.is_terminal is False


@pytest.mark.parametrize(
    "status",
    (
        ExecutionStepStatus.COMPLETED,
        ExecutionStepStatus.FAILED,
        ExecutionStepStatus.SKIPPED,
        ExecutionStepStatus.CANCELLED,
    ),
)
def test_identifies_terminal_step(
    status: ExecutionStepStatus,
) -> None:
    assert create_step(
        status=status
    ).is_terminal


@pytest.mark.parametrize(
    "field_name",
    (
        "id",
        "attempt_id",
        "step_number",
    ),
)
def test_rejects_invalid_step_identifier(
    field_name: str,
) -> None:
    values = {
        "id": 1,
        "attempt_id": 2,
        "step_number": 1,
    }
    values[field_name] = 0

    with pytest.raises(ValueError):
        ExecutionStep(
            **values,
            name="Crear estructura",
            action_type="filesystem",
            status=(
                ExecutionStepStatus.PENDING
            ),
            started_at=None,
            finished_at=None,
            exit_code=None,
            stdout_text=None,
            stderr_text=None,
            error_message=None,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "name",
        "action_type",
    ),
)
def test_rejects_empty_step_text(
    field_name: str,
) -> None:
    values = {
        "name": "Crear estructura",
        "action_type": "filesystem",
    }
    values[field_name] = "   "

    with pytest.raises(ValueError):
        ExecutionStep(
            id=1,
            attempt_id=2,
            step_number=1,
            **values,
            status=(
                ExecutionStepStatus.PENDING
            ),
            started_at=None,
            finished_at=None,
            exit_code=None,
            stdout_text=None,
            stderr_text=None,
            error_message=None,
        )