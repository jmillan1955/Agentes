import subprocess
from pathlib import Path

import pytest

from app.execution.git_promotion import (
    GitPromotionBranchService,
    GitPromotionError,
)
from app.execution.git_repository import (
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

    run_git(path, "init", "-b", "main")
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
        "# Temporal\n",
        encoding="utf-8",
        newline="",
    )

    run_git(path, "add", "README.md")
    run_git(
        path,
        "commit",
        "-m",
        "Commit inicial",
    )

    return path


def create_service() -> (
    GitPromotionBranchService
):
    return GitPromotionBranchService(
        git_inspector=(
            GitRepositoryInspector()
        )
    )


def test_creates_promotion_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    base_commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    branch = create_service().create(
        repository_root=repository,
        branch_name=(
            "promotion/execution-1"
        ),
    )

    assert branch.base_branch == "main"
    assert (
        branch.promotion_branch
        == "promotion/execution-1"
    )
    assert branch.base_commit == base_commit

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "promotion/execution-1"

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == base_commit


@pytest.mark.parametrize(
    "branch_name",
    (
        "",
        "   ",
        "feature/execution-1",
        " promotion/execution-1",
        "promotion/execution-1 ",
        "promotion/../main",
        "promotion/execution 1",
        "promotion/execution-1.lock",
    ),
)
def test_rejects_unsafe_branch_name(
    branch_name: str,
) -> None:
    with pytest.raises(
        GitPromotionError
    ):
        create_service().create(
            repository_root=Path("."),
            branch_name=branch_name,
        )


def test_rejects_existing_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    run_git(
        repository,
        "branch",
        "promotion/execution-1",
    )

    with pytest.raises(
        GitPromotionError,
        match="ya existe",
    ):
        create_service().create(
            repository_root=repository,
            branch_name=(
                "promotion/execution-1"
            ),
        )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"


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
        GitPromotionError,
        match="cambios sin confirmar",
    ):
        create_service().create(
            repository_root=repository,
            branch_name=(
                "promotion/execution-1"
            ),
        )


def test_rolls_back_empty_promotion_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    service = create_service()

    branch = service.create(
        repository_root=repository,
        branch_name=(
            "promotion/execution-1"
        ),
    )

    service.rollback(branch)

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"

    assert run_git(
        repository,
        "branch",
        "--list",
        "promotion/execution-1",
    ) == ""


def test_rejects_rollback_with_commit(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    service = create_service()

    branch = service.create(
        repository_root=repository,
        branch_name=(
            "promotion/execution-1"
        ),
    )

    (repository / "nuevo.py").write_text(
        "NUEVO = True\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "nuevo.py")
    run_git(
        repository,
        "commit",
        "-m",
        "Cambio en promocion",
    )

    with pytest.raises(
        GitPromotionError,
        match="contiene commits",
    ):
        service.rollback(branch)

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "promotion/execution-1"


def test_rejects_rollback_from_other_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    service = create_service()

    branch = service.create(
        repository_root=repository,
        branch_name=(
            "promotion/execution-1"
        ),
    )

    run_git(repository, "switch", "main")

    with pytest.raises(
        GitPromotionError,
        match="rama activa",
    ):
        service.rollback(branch)