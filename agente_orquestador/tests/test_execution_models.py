import pytest

from app.execution.models import (
    ExecutionStatus,
    TaskExecution,
)


def create_execution(
    status: ExecutionStatus = (
        ExecutionStatus.PREPARED
    ),
    attempt_count: int = 0,
) -> TaskExecution:
    return TaskExecution(
        id=1,
        task_id=3,
        plan_id=7,
        approval_id=1,
        status=status,
        workspace_path=(
            " C:\\proyectos\\temporal "
        ),
        requested_by_user_id=" 123456 ",
        request_message_id=" mensaje-1 ",
        channel=" telegram ",
        attempt_count=attempt_count,
        created_at=(
            "2026-08-27T06:00:00.000Z"
        ),
        started_at=None,
        finished_at=None,
        last_error=None,
    )


def test_creates_normalized_execution() -> None:
    execution = create_execution()

    assert execution.id == 1
    assert execution.task_id == 3
    assert execution.plan_id == 7
    assert execution.approval_id == 1
    assert (
        execution.status
        == ExecutionStatus.PREPARED
    )
    assert (
        execution.workspace_path
        == "C:\\proyectos\\temporal"
    )
    assert (
        execution.requested_by_user_id
        == "123456"
    )
    assert execution.channel == "telegram"
    assert execution.attempt_count == 0
    assert execution.is_terminal is False
    assert execution.can_resume is False


@pytest.mark.parametrize(
    "field_name",
    (
        "id",
        "task_id",
        "plan_id",
        "approval_id",
    ),
)
def test_rejects_non_positive_identifier(
    field_name: str,
) -> None:
    values = {
        "id": 1,
        "task_id": 3,
        "plan_id": 7,
        "approval_id": 1,
    }
    values[field_name] = 0

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} debe ser "
            "mayor que cero"
        ),
    ):
        TaskExecution(
            **values,
            status=ExecutionStatus.PREPARED,
            workspace_path="temporal",
            requested_by_user_id="123456",
            request_message_id="mensaje-1",
            channel="telegram",
            attempt_count=0,
            created_at=(
                "2026-08-27T06:00:00.000Z"
            ),
            started_at=None,
            finished_at=None,
            last_error=None,
        )


def test_rejects_negative_attempt_count() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "attempt_count no puede ser "
            "negativo"
        ),
    ):
        create_execution(
            attempt_count=-1
        )


def test_identifies_terminal_statuses() -> None:
    completed = create_execution(
        status=ExecutionStatus.COMPLETED
    )
    cancelled = create_execution(
        status=ExecutionStatus.CANCELLED
    )
    failed = create_execution(
        status=ExecutionStatus.FAILED
    )

    assert completed.is_terminal is True
    assert cancelled.is_terminal is True
    assert failed.is_terminal is False


def test_identifies_resumable_statuses() -> None:
    failed = create_execution(
        status=ExecutionStatus.FAILED
    )
    interrupted = create_execution(
        status=ExecutionStatus.INTERRUPTED
    )
    prepared = create_execution()

    assert failed.can_resume is True
    assert interrupted.can_resume is True
    assert prepared.can_resume is False