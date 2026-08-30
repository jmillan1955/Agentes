import subprocess
from pathlib import Path

import pytest

from app.execution.git_promotion import (
    GitPromotionBranchService,
)
from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.promotion_application import (
    PromotionApplicationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowError,
    PromotionWorkflowService,
)
from app.execution.workspace_package import (
    WorkspacePackager,
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

    (path / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
        newline="",
    )

    run_git(path, "add", ".")
    run_git(
        path,
        "commit",
        "-m",
        "Commit inicial",
    )

    return path


def create_workspace(
    path: Path,
) -> Path:
    path.mkdir()

    (path / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
        newline="",
    )

    tests = path / "tests"
    tests.mkdir()

    (tests / "test_suma.py").write_text(
        "from suma import sumar\n\n"
        "def test_sumar():\n"
        "    assert sumar(2, 3) == 5\n",
        encoding="utf-8",
        newline="",
    )

    return path


def create_services() -> tuple[
    PromotionPreviewService,
    PromotionWorkflowService,
]:
    inspector = GitRepositoryInspector()

    preview_service = (
        PromotionPreviewService(
            workspace_packager=(
                WorkspacePackager()
            )
        )
    )

    application_service = (
        PromotionApplicationService(
            preview_service=preview_service,
            git_inspector=inspector,
        )
    )

    branch_service = (
        GitPromotionBranchService(
            git_inspector=inspector
        )
    )

    workflow_service = (
        PromotionWorkflowService(
            branch_service=branch_service,
            application_service=(
                application_service
            ),
        )
    )

    return (
        preview_service,
        workflow_service,
    )


def test_applies_preview_on_temporary_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )

    preview_service, workflow_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )
    base_commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    result = (
        workflow_service
        .apply_to_temporary_branch(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )
    )

    expected_branch = (
        "promotion/"
        "execution-7-"
        f"{preview.preview_hash[:12]}"
    )

    assert (
        result.branch.promotion_branch
        == expected_branch
    )
    assert (
        result.application.branch_name
        == expected_branch
    )
    assert result.branch.base_commit == (
        base_commit
    )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == expected_branch

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == base_commit

    assert (
        repository / "suma.py"
    ).read_text(
        encoding="utf-8"
    ) == (
        "def sumar(a, b):\n"
        "    return a + b\n"
    )

    assert (
        repository
        / "tests"
        / "test_suma.py"
    ).is_file()

    assert run_git(
        repository,
        "status",
        "--porcelain",
    )


def test_removes_branch_after_invalid_hash(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )

    preview_service, workflow_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    with pytest.raises(
        PromotionWorkflowError,
        match="hash confirmado",
    ):
        workflow_service.apply_to_temporary_branch(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                "0" * 64
            ),
        )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"

    assert run_git(
        repository,
        "branch",
        "--list",
        "promotion/*",
    ) == ""

    assert (
        repository / "suma.py"
    ).read_text(
        encoding="utf-8"
    ) == (
        "def sumar(a, b):\n"
        "    return a - b\n"
    )


def test_removes_branch_after_stale_preview(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )

    preview_service, workflow_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    (workspace / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a * b\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        PromotionWorkflowError,
        match="han cambiado",
    ):
        workflow_service.apply_to_temporary_branch(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"

    assert run_git(
        repository,
        "branch",
        "--list",
        "promotion/*",
    ) == ""


@pytest.mark.parametrize(
    "execution_id",
    (
        0,
        -1,
    ),
)
def test_rejects_invalid_execution_id(
    tmp_path: Path,
    execution_id: int,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )

    preview_service, workflow_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    with pytest.raises(
        PromotionWorkflowError,
        match="execution_id",
    ):
        workflow_service.apply_to_temporary_branch(
            execution_id=execution_id,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"

def test_rolls_back_applied_workflow(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )

    preview_service, workflow_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    result = (
        workflow_service
        .apply_to_temporary_branch(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )
    )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ).startswith("promotion/")

    assert (
        repository / "tests" / "test_suma.py"
    ).is_file()

    workflow_service.rollback(result)

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"

    assert run_git(
        repository,
        "branch",
        "--list",
        "promotion/*",
    ) == ""

    assert (
        repository / "suma.py"
    ).read_text(
        encoding="utf-8"
    ) == (
        "def sumar(a, b):\n"
        "    return a - b\n"
    )

    assert not (
        repository / "tests" / "test_suma.py"
    ).exists()

    assert not (
        repository / "tests"
    ).exists()

    assert run_git(
        repository,
        "status",
        "--porcelain",
    ) == ""