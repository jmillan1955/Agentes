from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.manifest_service import (
    ExecutionManifestConfirmationError,
    ExecutionManifestService,
)

from app.execution.models import (
    ExecutionStatus,
)

def create_service(
    *,
    destructive_action_count: int = 0,
    authorized_user_id: str = "123456",
):
    execution_repository = Mock()
    approval_repository = Mock()
    manifest_repository = Mock()

    execution = SimpleNamespace(
        id=5,
        task_id=4,
        approval_id=2,
        status=ExecutionStatus.PREPARED,
    )

    approval = SimpleNamespace(
        id=2,
        authorized_user_id=(
            authorized_user_id
        ),
    )

    manifest = SimpleNamespace(
        id=7,
        execution_id=5,
        manifest_hash="a" * 64,
        destructive_action_count=(
            destructive_action_count
        ),
        is_confirmed=False,
        action_count=0,
        requires_extra_confirmation=(
            destructive_action_count > 0
        ),
    )

    execution_repository.get_by_task_id.return_value = (
        execution
    )
    approval_repository.get_by_task_id.return_value = (
        approval
    )
    manifest_repository.get_latest.return_value = (
        manifest
    )
    manifest_repository.list_actions.return_value = (
        ()
    )
    manifest_repository.confirm.return_value = (
        SimpleNamespace(
            id=7,
            execution_id=5,
            manifest_hash="a" * 64,
            destructive_action_count=(
                destructive_action_count
            ),
            is_confirmed=True,
        )
    )

    service = ExecutionManifestService(
        execution_repository=(
            execution_repository
        ),
        approval_repository=(
            approval_repository
        ),
        manifest_repository=(
            manifest_repository
        ),
    )

    return (
        service,
        execution_repository,
        approval_repository,
        manifest_repository,
        manifest,
    )


def test_gets_manifest_review_by_task() -> None:
    (
        service,
        _,
        _,
        manifest_repository,
        manifest,
    ) = create_service(
        destructive_action_count=1
    )

    result = service.get_by_task_id(4)

    assert result.manifest == manifest
    assert result.actions == ()
    assert (
        result.requires_extra_confirmation
        is True
    )

    manifest_repository.get_latest.assert_called_once_with(
        5
    )


def test_confirms_exact_non_destructive_manifest(
) -> None:
    (
        service,
        _,
        _,
        manifest_repository,
        _,
    ) = create_service()

    confirmed = service.confirm(
        task_id=4,
        expected_manifest_hash="a" * 64,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "mensaje-confirmacion-1"
        ),
        confirmation_channel="telegram",
        destructive_acknowledged=False,
    )

    assert confirmed.is_confirmed

    manifest_repository.confirm.assert_called_once_with(
        manifest_id=7,
        expected_manifest_hash="a" * 64,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "mensaje-confirmacion-1"
        ),
        confirmation_channel="telegram",
    )


def test_requires_destructive_acknowledgement(
) -> None:
    (
        service,
        _,
        _,
        manifest_repository,
        _,
    ) = create_service(
        destructive_action_count=1
    )

    with pytest.raises(
        ExecutionManifestConfirmationError,
        match=(
            "El manifiesto contiene acciones "
            "destructivas"
        ),
    ):
        service.confirm(
            task_id=4,
            expected_manifest_hash=(
                "a" * 64
            ),
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "mensaje-confirmacion-2"
            ),
            confirmation_channel=(
                "telegram"
            ),
            destructive_acknowledged=False,
        )

    manifest_repository.confirm.assert_not_called()


def test_rejects_confirmation_by_other_user(
) -> None:
    (
        service,
        _,
        _,
        manifest_repository,
        _,
    ) = create_service(
        authorized_user_id="123456"
    )

    with pytest.raises(
        ExecutionManifestConfirmationError,
        match=(
            "Solo el usuario que aprobo "
            "el plan puede confirmar"
        ),
    ):
        service.confirm(
            task_id=4,
            expected_manifest_hash=(
                "a" * 64
            ),
            confirmed_by_user_id="999999",
            confirmation_message_id=(
                "mensaje-confirmacion-3"
            ),
            confirmation_channel=(
                "telegram"
            ),
            destructive_acknowledged=False,
        )

    manifest_repository.confirm.assert_not_called()


def test_reports_task_without_execution() -> None:
    (
        service,
        execution_repository,
        _,
        _,
        _,
    ) = create_service()

    execution_repository.get_by_task_id.return_value = (
        None
    )

    with pytest.raises(
        ExecutionManifestConfirmationError,
        match=(
            "La tarea no tiene una "
            "ejecucion preparada"
        ),
    ):
        service.get_by_task_id(99)