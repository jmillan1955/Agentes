import subprocess
from pathlib import Path

import pytest

from app.execution.git_promotion import (
    GitPromotionBranchService,
)
from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.promotion_application import (
    PromotionApplicationService,
)
from app.execution.promotion_commit import (
    PromotionCommitService,
)
from app.execution.promotion_finalization import (
    PromotionFinalizationError,
    PromotionFinalizationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.promotion_validation import (
    PromotionValidationService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowService,
)
from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)


class FakeSandboxBackend:
    def __init__(
        self,
        result: SandboxRunResult,
    ) -> None:
        self._result = result
        self.requests: list[
            SandboxRunRequest
        ] = []

    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        self.requests.append(request)
        return self._result


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

    tests_directory = path / "tests"
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

    return path


def create_services(
    backend: FakeSandboxBackend,
) -> tuple[
    PromotionPreviewService,
    PromotionFinalizationService,
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

    validation_service = (
        PromotionValidationService(
            workflow_service=workflow_service,
            sandbox_backend=backend,
            limits=ExecutionLimits(
                command_timeout_seconds=30.0,
                max_output_characters=10_000,
            ),
        )
    )

    commit_service = PromotionCommitService(
        git_inspector=inspector
    )

    finalization_service = (
        PromotionFinalizationService(
            workflow_service=workflow_service,
            validation_service=(
                validation_service
            ),
            commit_service=commit_service,
        )
    )

    return (
        preview_service,
        finalization_service,
    )


def test_finalizes_real_promotion_flow(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    base_commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    sandbox_result = SandboxRunResult(
        exit_code=0,
        stdout_text="1 passed",
        stderr_text="",
        timed_out=False,
        duration_seconds=0.40,
    )
    backend = FakeSandboxBackend(
        sandbox_result
    )

    (
        preview_service,
        finalization_service,
    ) = create_services(backend)

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    result = finalization_service.finalize(
        execution_id=7,
        preview=preview,
        confirmed_preview_hash=(
            preview.preview_hash
        ),
        test_target="tests",
    )

    expected_branch = (
        "promotion/"
        "execution-7-"
        f"{preview.preview_hash[:12]}"
    )

    assert (
        result.commit.branch_name
        == expected_branch
    )
    assert (
        result.commit.base_commit
        == base_commit
    )
    assert (
        result.commit.commit_hash
        != base_commit
    )
    assert result.commit.committed_paths == (
        "suma.py",
        "tests/test_suma.py",
    )

    assert run_git(
        repository,
        "branch",
        "--show-current",
    ) == expected_branch

    assert run_git(
        repository,
        "status",
        "--porcelain",
    ) == ""

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

    assert run_git(
        repository,
        "log",
        "-1",
        "--pretty=%s",
    ) == "Promocionar ejecucion #7"

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

    assert len(backend.requests) == 1
    assert (
        backend.requests[0].workspace_path
        == repository.resolve()
    )
    assert (
        backend.requests[0].test_target
        == "tests"
    )


def test_rolls_back_real_flow_after_failed_tests(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    base_commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    sandbox_result = SandboxRunResult(
        exit_code=1,
        stdout_text="1 failed",
        stderr_text="AssertionError",
        timed_out=False,
        duration_seconds=0.45,
    )
    backend = FakeSandboxBackend(
        sandbox_result
    )

    (
        preview_service,
        finalization_service,
    ) = create_services(backend)

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    with pytest.raises(
        PromotionFinalizationError,
        match="no supero la validacion",
    ) as error_info:
        finalization_service.finalize(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
            test_target="tests",
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
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

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == base_commit

    assert run_git(
        repository,
        "status",
        "--porcelain",
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
        repository
        / "tests"
        / "test_suma.py"
    ).exists()

    assert not (
        repository / "tests"
    ).exists()

    assert len(backend.requests) == 1