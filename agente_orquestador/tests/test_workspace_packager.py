import base64
from pathlib import Path

import pytest

from app.execution.workspace_package import (
    WorkspacePackager,
    WorkspacePackagingError,
)


def test_packages_only_allowed_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    tests = workspace / "tests"
    tests.mkdir(parents=True)

    (tests / "test_ok.py").write_text(
        "def test_ok(): pass\n",
        encoding="utf-8",
        newline="",
    )
    (workspace / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n",
        encoding="utf-8",
    )
    (workspace / ".env").write_text(
        "SECRETO=no_enviar\n",
        encoding="utf-8",
    )

    cache = workspace / "__pycache__"
    cache.mkdir()
    (cache / "modulo.py").write_text(
        "secreto",
        encoding="utf-8",
    )

    files = WorkspacePackager().package(
        workspace
    )

    paths = tuple(
        file.relative_path
        for file in files
    )

    assert paths == (
        "pyproject.toml",
        "tests/test_ok.py",
    )

    decoded = base64.b64decode(
        files[1].content_base64
    ).decode("utf-8")

    assert decoded == "def test_ok(): pass\n"


def test_rejects_too_many_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "uno.py").write_text(
        "1",
        encoding="utf-8",
    )
    (workspace / "dos.py").write_text(
        "2",
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspacePackagingError,
        match="numero maximo",
    ):
        WorkspacePackager(
            max_files=1
        ).package(workspace)


def test_rejects_total_size(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "grande.py").write_text(
        "12345",
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspacePackagingError,
        match="tamano maximo",
    ):
        WorkspacePackager(
            max_total_bytes=4
        ).package(workspace)


def test_rejects_empty_allowed_package(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / ".env").write_text(
        "SECRETO=valor",
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspacePackagingError,
        match="no contiene archivos",
    ):
        WorkspacePackager().package(
            workspace
        )