from pathlib import Path

import pytest

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.filesystem_executor import (
    FilesystemExecutionError,
    SafeFilesystemExecutor,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.workspace import (
    WorkspacePolicy,
    WorkspaceViolationError,
)


def create_executor(
    root: Path,
    max_file_bytes: int = 1_000_000,
) -> SafeFilesystemExecutor:
    return SafeFilesystemExecutor(
        workspace_policy=WorkspacePolicy(
            allowed_root=root
        ),
        limits=ExecutionLimits(
            max_text_file_bytes=(
                max_file_bytes
            )
        ),
    )


def test_creates_workspace_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    executor = create_executor(root)

    workspace_result = executor.execute(
        workspace_path=workspace,
        action=ExecutionAction(
            step_number=1,
            name="Crear workspace",
            action_type=(
                ExecutionActionType
                .CREATE_DIRECTORY
            ),
            relative_path=".",
        ),
    )

    source_result = executor.execute(
        workspace_path=workspace,
        action=ExecutionAction(
            step_number=2,
            name="Crear src",
            action_type=(
                ExecutionActionType
                .CREATE_DIRECTORY
            ),
            relative_path="src",
        ),
    )

    assert workspace_result.created is True
    assert source_result.created is True
    assert workspace.is_dir()
    assert (workspace / "src").is_dir()


def test_writes_text_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    (workspace / "src").mkdir(
        parents=True
    )
    executor = create_executor(root)

    result = executor.execute(
        workspace_path=workspace,
        action=ExecutionAction(
            step_number=1,
            name="Crear modulo",
            action_type=(
                ExecutionActionType
                .WRITE_TEXT_FILE
            ),
            relative_path="src/main.py",
            content="print('hola')\n",
        ),
    )

    assert result.created is True
    assert result.bytes_written > 0
    assert (
        workspace / "src" / "main.py"
    ).read_text(
        encoding="utf-8"
    ) == "print('hola')\n"


def test_same_file_is_idempotent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    workspace.mkdir(parents=True)
    executor = create_executor(root)

    action = ExecutionAction(
        step_number=1,
        name="Crear README",
        action_type=(
            ExecutionActionType
            .WRITE_TEXT_FILE
        ),
        relative_path="README.md",
        content="# Temporal\n",
    )

    first = executor.execute(
        workspace,
        action,
    )
    repeated = executor.execute(
        workspace,
        action,
    )

    assert first.created is True
    assert repeated.created is False
    assert repeated.bytes_written == 0


def test_rejects_overwrite_with_different_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    workspace.mkdir(parents=True)
    target = workspace / "README.md"
    target.write_text(
        "original",
        encoding="utf-8",
    )
    executor = create_executor(root)

    with pytest.raises(
        FilesystemExecutionError,
        match="No se permite sobrescribir",
    ):
        executor.execute(
            workspace_path=workspace,
            action=ExecutionAction(
                step_number=1,
                name="Cambiar README",
                action_type=(
                    ExecutionActionType
                    .WRITE_TEXT_FILE
                ),
                relative_path="README.md",
                content="modificado",
            ),
        )

    assert target.read_text(
        encoding="utf-8"
    ) == "original"


def test_rejects_file_over_size_limit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    workspace.mkdir(parents=True)
    executor = create_executor(
        root,
        max_file_bytes=4,
    )

    with pytest.raises(
        FilesystemExecutionError,
        match="supera el limite",
    ):
        executor.execute(
            workspace_path=workspace,
            action=ExecutionAction(
                step_number=1,
                name="Crear archivo grande",
                action_type=(
                    ExecutionActionType
                    .WRITE_TEXT_FILE
                ),
                relative_path="grande.txt",
                content="12345",
            ),
        )


def test_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"
    executor = create_executor(root)

    with pytest.raises(
        WorkspaceViolationError
    ):
        executor.execute(
            workspace_path=workspace,
            action=ExecutionAction(
                step_number=1,
                name="Escapar",
                action_type=(
                    ExecutionActionType
                    .WRITE_TEXT_FILE
                ),
                relative_path="../fuera.txt",
                content="prohibido",
            ),
        )