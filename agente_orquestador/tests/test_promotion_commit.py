import subprocess
from pathlib import Path

import pytest

from app.execution.git_promotion import (
    GitPromotionBranch,
)
from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.promotion_application import (
    PromotionApplicationResult,
)
from app.execution.promotion_commit import (
    PromotionCommitError,
    PromotionCommitService,
)
from app.execution.promotion_validation import (
    PromotionValidationResult,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowResult,
)
from app.execution.sandbox import (
    SandboxRunResult,
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

    (path / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
        newline="",
    )

    run_git(
        path,
        "add",
        "suma.py",
    )
    run_git(
        path,
        "commit",
        "-m",
        "Commit inicial",
    )

    return path


def create_validation(
    repository: Path,
    sandbox_result: (
        SandboxRunResult | None
    ) = None,
) -> PromotionValidationResult:
    base_commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    promotion_branch = (
        "promotion/execution-7"
    )

    run_git(
        repository,
        "switch",
        "-c",
        promotion_branch,
    )

    (repository / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
        newline="",
    )

    tests_directory = repository / "tests"
    tests_directory.mkdir()

    (
        tests_directory / "test_suma.py"
    ).write_text(
        "from suma import sumar\n\n"
        "def test_sumar():\n"
        "    assert sumar(2, 3) == 5\n",
        encoding="utf-8",
        newline="",
    )

    branch = GitPromotionBranch(
        repository_root=repository.resolve(),
        base_branch="main",
        promotion_branch=promotion_branch,
        base_commit=base_commit,
    )

    application = PromotionApplicationResult(
        repository_root=repository.resolve(),
        preview_hash="a" * 64,
        branch_name=promotion_branch,
        head_commit=base_commit,
        written_paths=(
            "suma.py",
            "tests/test_suma.py",
        ),
        added_count=1,
        modified_count=1,
        rollback_entries=(),
    )

    workflow_result = (
        PromotionWorkflowResult(
            branch=branch,
            application=application,
        )
    )

    return PromotionValidationResult(
        workflow_result=workflow_result,
        sandbox_result=(
            sandbox_result
            or SandboxRunResult(
                exit_code=0,
                stdout_text="1 passed",
                stderr_text="",
                timed_out=False,
                duration_seconds=0.25,
            )
        ),
        test_target="tests",
    )


def create_service() -> (
    PromotionCommitService
):
    return PromotionCommitService(
        git_inspector=(
            GitRepositoryInspector()
        )
    )


def test_commits_validated_promotion(
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
    validation = create_validation(
        repository
    )

    result = create_service().commit(
        execution_id=7,
        validation=validation,
    )

    assert (
        result.repository_root
        == repository.resolve()
    )
    assert (
        result.branch_name
        == "promotion/execution-7"
    )
    assert result.base_commit == base_commit
    assert (
        result.commit_message
        == "Promocionar ejecucion #7"
    )
    assert result.committed_paths == (
        "suma.py",
        "tests/test_suma.py",
    )

    assert (
        result.commit_hash
        == run_git(
            repository,
            "rev-parse",
            "HEAD",
        )
    )
    assert result.commit_hash != base_commit

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "promotion/execution-7"

    assert run_git(
        repository,
        "status",
        "--porcelain",
    ) == ""

    assert run_git(
        repository,
        "log",
        "-1",
        "--pretty=%s",
    ) == "Promocionar ejecucion #7"

    assert run_git(
        repository,
        "rev-parse",
        "HEAD^",
    ) == base_commit

    assert run_git(
        repository,
        "rev-parse",
        "main",
    ) == base_commit


def test_rejects_unexpected_repository_change(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    validation = create_validation(
        repository
    )
    base_commit = (
        validation
        .workflow_result
        .branch
        .base_commit
    )

    (repository / "inesperado.py").write_text(
        "INESPERADO = True\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        PromotionCommitError,
        match="distintos",
    ):
        create_service().commit(
            execution_id=7,
            validation=validation,
        )

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == base_commit

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "promotion/execution-7"

    status = run_git(
        repository,
        "status",
        "--porcelain",
    )

    assert "inesperado.py" in status


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
    validation = create_validation(
        repository
    )

    with pytest.raises(
        PromotionCommitError,
        match="execution_id",
    ):
        create_service().commit(
            execution_id=execution_id,
            validation=validation,
        )

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == (
        validation
        .workflow_result
        .branch
        .base_commit
    )


def test_rejects_failed_validation(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )

    validation = create_validation(
        repository=repository,
        sandbox_result=SandboxRunResult(
            exit_code=1,
            stdout_text="1 failed",
            stderr_text="AssertionError",
            timed_out=False,
            duration_seconds=0.30,
        ),
    )

    with pytest.raises(
        PromotionCommitError,
        match="validacion satisfactoria",
    ):
        create_service().commit(
            execution_id=7,
            validation=validation,
        )

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == (
        validation
        .workflow_result
        .branch
        .base_commit
    )


def test_rejects_changed_head_commit(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    validation = create_validation(
        repository
    )
    expected_base = (
        validation
        .workflow_result
        .branch
        .base_commit
    )

    run_git(
        repository,
        "add",
        "suma.py",
        "tests/test_suma.py",
    )
    run_git(
        repository,
        "commit",
        "-m",
        "Commit ajeno",
    )

    with pytest.raises(
        PromotionCommitError,
        match="commit base cambio",
    ):
        create_service().commit(
            execution_id=7,
            validation=validation,
        )

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) != expected_base


def test_rejects_other_active_branch(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    validation = create_validation(
        repository
    )

    run_git(
        repository,
        "stash",
        "push",
        "--include-untracked",
        "-m",
        "Cambios de prueba",
    )
    run_git(
        repository,
        "switch",
        "main",
    )

    with pytest.raises(
        PromotionCommitError,
        match="rama activa",
    ):
        create_service().commit(
            execution_id=7,
            validation=validation,
        )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == "main"