import subprocess
from pathlib import Path

import pytest

from app.execution.git_repository import (
    GitRepositoryInspectionError,
    GitRepositoryInspector,
)


def run_git(
    repository: Path,
    *arguments: str,
) -> str:
    result = subprocess.run(
        (
            "git",
            "-C",
            str(repository),
            *arguments,
        ),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return result.stdout.strip()


def create_repository(
    path: Path,
) -> Path:
    path.mkdir()

    run_git(
        path,
        "init",
        "-b",
        "main",
    )
    run_git(
        path,
        "config",
        "user.name",
        "Usuario de prueba",
    )
    run_git(
        path,
        "config",
        "user.email",
        "prueba@example.com",
    )

    (path / "README.md").write_text(
        "# Repositorio temporal\n",
        encoding="utf-8",
        newline="",
    )

    run_git(
        path,
        "add",
        "README.md",
    )
    run_git(
        path,
        "commit",
        "-m",
        "Commit inicial",
    )

    return path


def test_inspects_clean_repository(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    state = GitRepositoryInspector().inspect(
        repository
    )

    assert (
        state.repository_root
        == repository.resolve()
    )
    assert state.current_branch == "main"
    assert state.head_commit == run_git(
        repository,
        "rev-parse",
        "HEAD",
    )
    assert state.is_clean is True


def test_rejects_dirty_repository(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    (repository / "nuevo.py").write_text(
        "NUEVO = True\n",
        encoding="utf-8",
    )

    with pytest.raises(
        GitRepositoryInspectionError,
        match="cambios sin confirmar",
    ):
        GitRepositoryInspector().inspect(
            repository
        )


def test_reports_dirty_repository_when_allowed(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    (repository / "nuevo.py").write_text(
        "NUEVO = True\n",
        encoding="utf-8",
    )

    state = GitRepositoryInspector().inspect(
        repository_root=repository,
        require_clean=False,
    )

    assert state.is_clean is False


def test_rejects_non_repository(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(
        GitRepositoryInspectionError,
        match="Git no pudo inspeccionar",
    ):
        GitRepositoryInspector().inspect(
            directory
        )


def test_rejects_repository_subdirectory(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    subdirectory = repository / "src"
    subdirectory.mkdir()

    with pytest.raises(
        GitRepositoryInspectionError,
        match="raiz exacta",
    ):
        GitRepositoryInspector().inspect(
            subdirectory
        )


def test_rejects_detached_head(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    run_git(
        repository,
        "checkout",
        "--detach",
        "HEAD",
    )

    with pytest.raises(
        GitRepositoryInspectionError,
        match="detached HEAD",
    ):
        GitRepositoryInspector().inspect(
            repository
        )


def test_rejects_repository_without_commit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    run_git(
        repository,
        "init",
        "-b",
        "main",
    )

    with pytest.raises(
        GitRepositoryInspectionError,
        match=(
            "Git no pudo inspeccionar"
            "|commit inicial"
        ),
    ):
        GitRepositoryInspector().inspect(
            repository
        )