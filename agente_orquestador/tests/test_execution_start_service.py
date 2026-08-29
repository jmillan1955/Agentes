from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.manifest_models import (
    ExecutionManifestStatus,
)
from app.execution.models import (
    ExecutionStatus,
)
from app.execution.start_service import (
    ExecutionStartError,
    ExecutionStartService,
)


def create_service():
    execution_repository = Mock()
    manifest_repository = Mock()
    runner = Mock()

    service = ExecutionStartService(
        execution_repository=(
            execution_repository
        ),
        manifest_repository=(
            manifest_repository
        ),
        runner=runner,
    )

    return (
        service,
        execution_repository,
        manifest_repository,
        runner,
    )


def create_prepared_execution():
    return SimpleNamespace(
        id=5,
        task_id=3,
        plan_id=7,
        status=ExecutionStatus.PREPARED,
    )


def create_confirmed_manifest():
    return SimpleNamespace(
        id=11,
        execution_id=5,
        version=2,
        status=(
            ExecutionManifestStatus.CONFIRMED
        ),
        manifest_hash="a" * 64,
        confirmed_by_user_id="123456",
    )


def test_starts_only_confirmed_actions() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution = create_prepared_execution()
    manifest = create_confirmed_manifest()

    actions = (
        SimpleNamespace(step_number=1),
        SimpleNamespace(step_number=2),
    )

    run_result = SimpleNamespace(
        execution=SimpleNamespace(
            id=5,
            task_id=3,
            status=ExecutionStatus.COMPLETED,
        ),
        attempt=SimpleNamespace(
            id=21,
            attempt_number=1,
            status=SimpleNamespace(
                value="completed"
            ),
        ),
        steps=(
            SimpleNamespace(),
            SimpleNamespace(),
        ),
    )

    execution_repository.get_by_task_id.return_value = (
        execution
    )
    manifest_repository.get_latest.return_value = (
        manifest
    )
    manifest_repository.load_confirmed_actions.return_value = (
        actions
    )
    runner.run.return_value = run_result

    result = service.start(
        task_id=3,
        requested_by_user_id="123456",
    )

    assert result.manifest is manifest
    assert result.actions == actions
    assert result.run_result is run_result

    execution_repository.get_by_task_id.assert_called_once_with(
        3
    )
    manifest_repository.get_latest.assert_called_once_with(
        5
    )
    manifest_repository.load_confirmed_actions.assert_called_once_with(
        5
    )
    runner.run.assert_called_once_with(
        execution_id=5,
        actions=actions,
    )


def test_rejects_unconfirmed_manifest() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        create_prepared_execution()
    )

    manifest_repository.get_latest.return_value = (
        SimpleNamespace(
            id=11,
            execution_id=5,
            status=(
                ExecutionManifestStatus
                .PENDING_CONFIRMATION
            ),
            confirmed_by_user_id=None,
        )
    )

    with pytest.raises(
        ExecutionStartError,
        match="manifiesto confirmado",
    ):
        service.start(
            task_id=3,
            requested_by_user_id="123456",
        )

    manifest_repository.load_confirmed_actions.assert_not_called()
    runner.run.assert_not_called()


def test_rejects_start_by_other_user() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        create_prepared_execution()
    )
    manifest_repository.get_latest.return_value = (
        create_confirmed_manifest()
    )

    with pytest.raises(
        ExecutionStartError,
        match=(
            "Solo el usuario que confirmo "
            "el manifiesto"
        ),
    ):
        service.start(
            task_id=3,
            requested_by_user_id="999999",
        )

    manifest_repository.load_confirmed_actions.assert_not_called()
    runner.run.assert_not_called()


def test_rejects_execution_not_prepared() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        SimpleNamespace(
            id=5,
            task_id=3,
            status=ExecutionStatus.CANCELLED,
        )
    )

    with pytest.raises(
        ExecutionStartError,
        match="ejecucion preparada",
    ):
        service.start(
            task_id=3,
            requested_by_user_id="123456",
        )

    manifest_repository.get_latest.assert_not_called()
    manifest_repository.load_confirmed_actions.assert_not_called()
    runner.run.assert_not_called()


def test_does_not_run_tampered_actions() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        create_prepared_execution()
    )
    manifest_repository.get_latest.return_value = (
        create_confirmed_manifest()
    )
    manifest_repository.load_confirmed_actions.side_effect = (
        RuntimeError(
            "Las acciones no coinciden con "
            "el hash del manifiesto"
        )
    )

    with pytest.raises(
        ExecutionStartError,
        match="hash del manifiesto",
    ):
        service.start(
            task_id=3,
            requested_by_user_id="123456",
        )

    runner.run.assert_not_called()

@pytest.mark.parametrize(
    "execution_status",
    (
        ExecutionStatus.FAILED,
        ExecutionStatus.INTERRUPTED,
    ),
)
def test_resumes_failed_or_interrupted_execution(
    execution_status: ExecutionStatus,
) -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution = SimpleNamespace(
        id=5,
        task_id=3,
        plan_id=7,
        status=execution_status,
    )
    manifest = create_confirmed_manifest()
    actions = (
        SimpleNamespace(step_number=1),
        SimpleNamespace(step_number=2),
    )
    run_result = SimpleNamespace(
        execution=SimpleNamespace(
            id=5,
            task_id=3,
            status=ExecutionStatus.COMPLETED,
        ),
        attempt=SimpleNamespace(
            id=22,
            attempt_number=2,
        ),
        steps=(),
    )

    execution_repository.get_by_task_id.return_value = (
        execution
    )
    manifest_repository.get_latest.return_value = (
        manifest
    )
    manifest_repository.load_confirmed_actions.return_value = (
        actions
    )
    runner.run.return_value = run_result

    result = service.resume(
        task_id=3,
        requested_by_user_id="123456",
    )

    assert result.manifest is manifest
    assert result.actions == actions
    assert result.run_result is run_result

    runner.run.assert_called_once_with(
        execution_id=5,
        actions=actions,
    )

@pytest.mark.parametrize(
    "execution_status",
    (
        ExecutionStatus.PREPARED,
        ExecutionStatus.RUNNING,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.CANCELLED,
    ),
)
def test_rejects_resume_for_non_resumable_status(
    execution_status: ExecutionStatus,
) -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        SimpleNamespace(
            id=5,
            task_id=3,
            status=execution_status,
        )
    )

    with pytest.raises(
        ExecutionStartError,
        match=(
            "ejecucion fallida o "
            "interrumpida"
        ),
    ):
        service.resume(
            task_id=3,
            requested_by_user_id="123456",
        )

    manifest_repository.get_latest.assert_not_called()
    manifest_repository.load_confirmed_actions.assert_not_called()
    runner.run.assert_not_called()


def test_rejects_resume_by_other_user() -> None:
    (
        service,
        execution_repository,
        manifest_repository,
        runner,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        SimpleNamespace(
            id=5,
            task_id=3,
            status=ExecutionStatus.FAILED,
        )
    )
    manifest_repository.get_latest.return_value = (
        create_confirmed_manifest()
    )

    with pytest.raises(
        ExecutionStartError,
        match=(
            "Solo el usuario que confirmo "
            "el manifiesto"
        ),
    ):
        service.resume(
            task_id=3,
            requested_by_user_id="999999",
        )

    manifest_repository.load_confirmed_actions.assert_not_called()
    runner.run.assert_not_called()