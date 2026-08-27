from pathlib import Path

import pytest

from app.context import (
    ContextDatabase,
    TaskExecutionManifestRepository,
)
from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.manifest_models import (
    ExecutionManifestStatus,
)
from tests.execution_support import (
    prepare_execution_context,
)


def create_actions() -> tuple[
    ExecutionAction,
    ...,
]:
    return (
        ExecutionAction(
            step_number=1,
            name="Crear directorio app",
            action_type=(
                ExecutionActionType
                .CREATE_DIRECTORY
            ),
            relative_path="app",
        ),
        ExecutionAction(
            step_number=2,
            name="Crear modulo principal",
            action_type=(
                ExecutionActionType
                .WRITE_TEXT_FILE
            ),
            relative_path="app/main.py",
            content=(
                "def answer():\n"
                "    return 42\n"
            ),
        ),
        ExecutionAction(
            step_number=3,
            name="Ejecutar pruebas",
            action_type=(
                ExecutionActionType.RUN_PYTEST
            ),
            relative_path="tests",
        ),
    )


def test_creates_versioned_manifest(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=(
                tmp_path / "workspace"
            ),
        )

        repository = (
            TaskExecutionManifestRepository(
                database
            )
        )

        manifest = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        stored_actions = (
            repository.list_actions(
                manifest.id
            )
        )

        assert manifest.version == 1
        assert (
            manifest.status
            == ExecutionManifestStatus
            .PENDING_CONFIRMATION
        )
        assert len(manifest.manifest_hash) == 64
        assert manifest.action_count == 3
        assert (
            manifest.destructive_action_count
            == 1
        )

        assert len(stored_actions) == 3
        assert (
            stored_actions[1].content_sha256
            is not None
        )
        assert stored_actions[1].destructive
        assert (
            repository.get_latest(
                context.execution.id
            )
            == manifest
        )


def test_versions_and_supersedes_manifest(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=(
                tmp_path / "workspace"
            ),
        )

        repository = (
            TaskExecutionManifestRepository(
                database
            )
        )

        first = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        second = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        stored_first = repository.get_by_id(
            first.id
        )

        assert stored_first is not None
        assert (
            stored_first.status
            == ExecutionManifestStatus
            .SUPERSEDED
        )
        assert second.version == 2
        assert (
            second.manifest_hash
            == first.manifest_hash
        )


def test_confirms_exact_manifest_hash(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=(
                tmp_path / "workspace"
            ),
        )

        repository = (
            TaskExecutionManifestRepository(
                database
            )
        )

        manifest = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        confirmed = repository.confirm(
            manifest_id=manifest.id,
            expected_manifest_hash=(
                manifest.manifest_hash
            ),
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "confirmacion-manifiesto-1"
            ),
            confirmation_channel="telegram",
        )

        assert confirmed.is_confirmed
        assert (
            confirmed.confirmed_by_user_id
            == "123456"
        )
        assert confirmed.confirmed_at is not None


def test_rejects_different_manifest_hash(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=(
                tmp_path / "workspace"
            ),
        )

        repository = (
            TaskExecutionManifestRepository(
                database
            )
        )

        manifest = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        with pytest.raises(
            ValueError,
            match=(
                "El hash del manifiesto "
                "no coincide"
            ),
        ):
            repository.confirm(
                manifest_id=manifest.id,
                expected_manifest_hash=(
                    "f" * 64
                ),
                confirmed_by_user_id=(
                    "123456"
                ),
                confirmation_message_id=(
                    "confirmacion-invalida"
                ),
                confirmation_channel=(
                    "telegram"
                ),
            )


def test_loads_actions_only_when_confirmed(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=(
                tmp_path / "workspace"
            ),
        )

        repository = (
            TaskExecutionManifestRepository(
                database
            )
        )

        manifest = repository.create(
            execution_id=(
                context.execution.id
            ),
            actions=create_actions(),
        )

        with pytest.raises(
            ValueError,
            match=(
                "El manifiesto no esta "
                "confirmado"
            ),
        ):
            repository.load_confirmed_actions(
                context.execution.id
            )

        repository.confirm(
            manifest_id=manifest.id,
            expected_manifest_hash=(
                manifest.manifest_hash
            ),
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "confirmacion-manifiesto-2"
            ),
            confirmation_channel="telegram",
        )

        loaded = (
            repository.load_confirmed_actions(
                context.execution.id
            )
        )

        assert loaded == create_actions()