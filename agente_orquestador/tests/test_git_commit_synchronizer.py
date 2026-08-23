import subprocess
from pathlib import Path

import pytest

from app.context import (
    ContextDatabase,
    GitCommitRepository,
    GitCommitSynchronizer,
    GitSynchronizationError,
    ProjectRepository,
)


def run_git(
    repository_root: Path,
    *arguments: str,
) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def create_git_repository(
    tmp_path: Path,
) -> tuple[Path, Path]:
    repository_root = tmp_path / "repository"
    project_root = (
        repository_root / "agente_orquestador"
    )

    project_root.mkdir(
        parents=True
    )

    run_git(
        repository_root,
        "init",
    )

    run_git(
        repository_root,
        "config",
        "user.name",
        "Usuario de pruebas",
    )

    run_git(
        repository_root,
        "config",
        "user.email",
        "pruebas@example.com",
    )

    document = project_root / "README.md"
    document.write_text(
        "# Agente Orquestador",
        encoding="utf-8",
    )

    run_git(
        repository_root,
        "add",
        ".",
    )

    run_git(
        repository_root,
        "commit",
        "-m",
        "Crear Agente Orquestador",
    )

    return repository_root, project_root


def create_synchronizer(
    project_root: Path,
) -> tuple[
    ContextDatabase,
    GitCommitRepository,
    GitCommitSynchronizer,
]:
    database = ContextDatabase(
        ":memory:"
    ).connect()

    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path=str(project_root),
    )

    repository = GitCommitRepository(
        database
    )

    synchronizer = GitCommitSynchronizer(
        repository=repository,
        project_id=project.id,
        project_root=project_root,
    )

    return (
        database,
        repository,
        synchronizer,
    )


def test_imports_project_commits(
    tmp_path: Path,
) -> None:
    _, project_root = create_git_repository(
        tmp_path
    )

    (
        database,
        repository,
        synchronizer,
    ) = create_synchronizer(project_root)

    try:
        result = synchronizer.synchronize()

        assert result.scanned == 1
        assert result.created == 1
        assert result.updated == 0

        commits = repository.list_by_project(1)

        assert len(commits) == 1
        assert (
            commits[0].subject
            == "Crear Agente Orquestador"
        )
        assert (
            commits[0].author_name
            == "Usuario de pruebas"
        )

    finally:
        database.close()


def test_detects_unchanged_commits(
    tmp_path: Path,
) -> None:
    _, project_root = create_git_repository(
        tmp_path
    )

    (
        database,
        _,
        synchronizer,
    ) = create_synchronizer(project_root)

    try:
        first = synchronizer.synchronize()
        second = synchronizer.synchronize()

        assert first.created == 1
        assert second.created == 0
        assert second.updated == 0
        assert second.unchanged == 1

    finally:
        database.close()


def test_imports_only_commits_affecting_project(
    tmp_path: Path,
) -> None:
    (
        repository_root,
        project_root,
    ) = create_git_repository(tmp_path)

    unrelated = repository_root / "otro.txt"
    unrelated.write_text(
        "Otro proyecto",
        encoding="utf-8",
    )

    run_git(
        repository_root,
        "add",
        ".",
    )

    run_git(
        repository_root,
        "commit",
        "-m",
        "Modificar otro proyecto",
    )

    (
        database,
        repository,
        synchronizer,
    ) = create_synchronizer(project_root)

    try:
        result = synchronizer.synchronize()
        commits = repository.list_by_project(1)

        assert result.scanned == 1
        assert len(commits) == 1
        assert (
            commits[0].subject
            == "Crear Agente Orquestador"
        )

    finally:
        database.close()


def test_rejects_directory_outside_git(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "sin_git"
    project_root.mkdir()

    (
        database,
        _,
        synchronizer,
    ) = create_synchronizer(project_root)

    try:
        with pytest.raises(
            GitSynchronizationError,
            match="Git no pudo completar",
        ):
            synchronizer.synchronize()

    finally:
        database.close()