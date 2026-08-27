from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.models import (
    ExecutionStatus,
    TaskExecution,
)
from app.execution.service import (
    ExecutionPreparationError,
    ExecutionPreparationService,
)
from app.execution.workspace import (
    WorkspacePolicy,
)


def create_execution(
    workspace_path: Path,
) -> TaskExecution:
    return TaskExecution(
        id=1,
        task_id=3,
        plan_id=7,
        approval_id=1,
        status=ExecutionStatus.PREPARED,
        workspace_path=str(workspace_path),
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


def create_service(
    tmp_path: Path,
    task=None,
    approval=None,
    existing=None,
):
    task_repository = Mock()
    approval_repository = Mock()
    execution_repository = Mock()

    task_repository.get_by_id.return_value = (
        task
    )
    approval_repository.get_by_task_id.return_value = (
        approval
    )
    execution_repository.get_by_task_id.return_value = (
        existing
    )

    workspace_policy = WorkspacePolicy(
        allowed_root=tmp_path
    )

    service = ExecutionPreparationService(
        task_repository=task_repository,
        approval_repository=(
            approval_repository
        ),
        execution_repository=(
            execution_repository
        ),
        workspace_policy=workspace_policy,
    )

    return (
        service,
        task_repository,
        approval_repository,
        execution_repository,
    )


def test_prepares_derived_workspace_without_creating_it(
    tmp_path: Path,
) -> None:
    task = SimpleNamespace(
        id=3,
        target_project_name=(
            "proyecto_temporal"
        ),
    )
    approval = SimpleNamespace(
        id=1,
        plan_id=7,
    )
    expected_workspace = (
        tmp_path / "proyecto_temporal"
    ).resolve()
    execution = create_execution(
        expected_workspace
    )

    (
        service,
        _,
        _,
        execution_repository,
    ) = create_service(
        tmp_path=tmp_path,
        task=task,
        approval=approval,
    )

    execution_repository.prepare.return_value = (
        execution
    )

    result = service.prepare(
        task_id=3,
        requested_by_user_id="123456",
        request_message_id="mensaje-1",
        channel="telegram",
    )

    assert result.execution == execution
    assert result.already_prepared is False
    assert expected_workspace.exists() is False

    execution_repository.prepare.assert_called_once_with(
        task_id=3,
        plan_id=7,
        approval_id=1,
        workspace_path=str(
            expected_workspace
        ),
        requested_by_user_id="123456",
        request_message_id="mensaje-1",
        channel="telegram",
    )


def test_reports_existing_preparation(
    tmp_path: Path,
) -> None:
    task = SimpleNamespace(
        id=3,
        target_project_name=(
            "proyecto_temporal"
        ),
    )
    approval = SimpleNamespace(
        id=1,
        plan_id=7,
    )
    workspace = (
        tmp_path / "proyecto_temporal"
    ).resolve()
    existing = create_execution(workspace)

    (
        service,
        _,
        _,
        execution_repository,
    ) = create_service(
        tmp_path=tmp_path,
        task=task,
        approval=approval,
        existing=existing,
    )

    execution_repository.prepare.return_value = (
        existing
    )

    result = service.prepare(
        task_id=3,
        requested_by_user_id="123456",
        request_message_id="mensaje-2",
        channel="telegram",
    )

    assert result.execution == existing
    assert result.already_prepared is True


def test_rejects_unknown_task(
    tmp_path: Path,
) -> None:
    service, _, _, _ = create_service(
        tmp_path=tmp_path,
        task=None,
    )

    with pytest.raises(
        ExecutionPreparationError,
        match="No existe la tarea",
    ):
        service.prepare(
            task_id=99,
            requested_by_user_id="123456",
            request_message_id="mensaje-3",
            channel="telegram",
        )


def test_rejects_task_without_target_project(
    tmp_path: Path,
) -> None:
    task = SimpleNamespace(
        id=3,
        target_project_name=None,
    )

    service, _, _, _ = create_service(
        tmp_path=tmp_path,
        task=task,
    )

    with pytest.raises(
        ExecutionPreparationError,
        match=(
            "no tiene un proyecto objetivo"
        ),
    ):
        service.prepare(
            task_id=3,
            requested_by_user_id="123456",
            request_message_id="mensaje-4",
            channel="telegram",
        )


def test_rejects_task_without_approval(
    tmp_path: Path,
) -> None:
    task = SimpleNamespace(
        id=3,
        target_project_name=(
            "proyecto_temporal"
        ),
    )

    service, _, _, _ = create_service(
        tmp_path=tmp_path,
        task=task,
        approval=None,
    )

    with pytest.raises(
        ExecutionPreparationError,
        match="no tiene una autorizacion",
    ):
        service.prepare(
            task_id=3,
            requested_by_user_id="123456",
            request_message_id="mensaje-5",
            channel="telegram",
        )