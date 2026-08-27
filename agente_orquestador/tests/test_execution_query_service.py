from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.query import (
    ExecutionQueryError,
    ExecutionQueryService,
)


def test_gets_execution_attempts_and_steps(
) -> None:
    execution_repository = Mock()
    attempt_repository = Mock()
    step_repository = Mock()

    execution = SimpleNamespace(
        id=5,
        task_id=4,
    )

    first_attempt = SimpleNamespace(id=10)
    second_attempt = SimpleNamespace(id=11)

    first_step = SimpleNamespace(
        id=20,
        attempt_id=10,
    )
    second_step = SimpleNamespace(
        id=21,
        attempt_id=11,
    )

    execution_repository.get_by_task_id.return_value = (
        execution
    )
    attempt_repository.list_by_execution.return_value = (
        first_attempt,
        second_attempt,
    )
    step_repository.list_by_attempt.side_effect = (
        (first_step,),
        (second_step,),
    )

    service = ExecutionQueryService(
        execution_repository=(
            execution_repository
        ),
        attempt_repository=attempt_repository,
        step_repository=step_repository,
    )

    result = service.get_by_task_id(4)

    assert result.execution == execution
    assert result.attempts == (
        first_attempt,
        second_attempt,
    )
    assert result.steps == (
        first_step,
        second_step,
    )

    execution_repository.get_by_task_id.assert_called_once_with(
        4
    )
    attempt_repository.list_by_execution.assert_called_once_with(
        5
    )
    assert (
        step_repository
        .list_by_attempt.call_count
        == 2
    )


def test_reports_execution_without_attempts(
) -> None:
    execution_repository = Mock()
    attempt_repository = Mock()
    step_repository = Mock()

    execution_repository.get_by_task_id.return_value = (
        SimpleNamespace(
            id=5,
            task_id=4,
        )
    )
    attempt_repository.list_by_execution.return_value = ()

    service = ExecutionQueryService(
        execution_repository=(
            execution_repository
        ),
        attempt_repository=attempt_repository,
        step_repository=step_repository,
    )

    result = service.get_by_task_id(4)

    assert result.attempts == ()
    assert result.steps == ()
    step_repository.list_by_attempt.assert_not_called()


@pytest.mark.parametrize(
    "task_id",
    (
        0,
        -1,
    ),
)
def test_rejects_invalid_task_id(
    task_id: int,
) -> None:
    service = ExecutionQueryService(
        execution_repository=Mock(),
        attempt_repository=Mock(),
        step_repository=Mock(),
    )

    with pytest.raises(
        ExecutionQueryError,
        match=(
            "El identificador de la tarea "
            "debe ser mayor que cero"
        ),
    ):
        service.get_by_task_id(task_id)


def test_reports_missing_execution() -> None:
    execution_repository = Mock()
    execution_repository.get_by_task_id.return_value = (
        None
    )

    service = ExecutionQueryService(
        execution_repository=(
            execution_repository
        ),
        attempt_repository=Mock(),
        step_repository=Mock(),
    )

    with pytest.raises(
        ExecutionQueryError,
        match=(
            "La tarea no tiene una "
            "ejecucion preparada"
        ),
    ):
        service.get_by_task_id(99)