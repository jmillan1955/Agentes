import subprocess
from pathlib import Path

import pytest

from app.context.database import (
    ContextDatabase,
)
from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.execution.audited_promotion_finalization import (
    AuditedPromotionFinalizationError,
    AuditedPromotionFinalizationService,
)
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
from app.execution.promotion_preparation import (
    PromotionPreparationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.promotion_records import (
    PromotionStatus,
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

    run_git(path, "add", "suma.py")
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


def prepare_completed_execution(
    database: ContextDatabase,
    workspace_path: Path,
) -> int:
    connection = database.connection

    project_cursor = connection.execute(
        """
        INSERT INTO projects (
            name,
            root_path,
            git_repository
        )
        VALUES (?, ?, ?)
        """,
        (
            "proyecto-temporal",
            str(workspace_path.parent),
            "repositorio-temporal",
        ),
    )
    project_id = int(
        project_cursor.lastrowid
    )

    session_cursor = connection.execute(
        """
        INSERT INTO sessions (
            project_id,
            channel,
            user_id,
            conversation_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            project_id,
            "telegram",
            "123456",
            "chat-temporal",
        ),
    )
    session_id = int(
        session_cursor.lastrowid
    )

    task_cursor = connection.execute(
        """
        INSERT INTO tasks (
            project_id,
            session_id,
            source_message_id,
            title,
            description,
            target_project_name,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            session_id,
            "telegram:tarea:1",
            "Tarea temporal",
            "Descripcion temporal",
            "proyecto-temporal",
            "completed",
        ),
    )
    task_id = int(
        task_cursor.lastrowid
    )

    plan_cursor = connection.execute(
        """
        INSERT INTO task_plans (
            task_id,
            version,
            status,
            objective
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            task_id,
            1,
            "approved",
            "Crear una suma",
        ),
    )
    plan_id = int(
        plan_cursor.lastrowid
    )

    approval_cursor = connection.execute(
        """
        INSERT INTO task_approvals (
            task_id,
            plan_id,
            plan_version,
            authorized_user_id,
            authorization_message_id,
            channel
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            plan_id,
            1,
            "123456",
            "telegram:aprobacion:1",
            "telegram",
        ),
    )
    approval_id = int(
        approval_cursor.lastrowid
    )

    execution_cursor = connection.execute(
        """
        INSERT INTO task_executions (
            task_id,
            plan_id,
            approval_id,
            status,
            workspace_path,
            requested_by_user_id,
            request_message_id,
            channel,
            attempt_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            plan_id,
            approval_id,
            "completed",
            str(workspace_path),
            "123456",
            "telegram:ejecucion:1",
            "telegram",
            1,
        ),
    )

    connection.commit()

    return int(
        execution_cursor.lastrowid
    )


def create_services(
    database: ContextDatabase,
    backend: FakeSandboxBackend,
) -> tuple[
    PromotionPreparationService,
    AuditedPromotionFinalizationService,
    TaskExecutionPromotionRepository,
]:
    inspector = GitRepositoryInspector()

    execution_repository = (
        TaskExecutionRepository(
            database
        )
    )
    promotion_repository = (
        TaskExecutionPromotionRepository(
            database
        )
    )
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
            limits=ExecutionLimits(),
        )
    )
    commit_service = PromotionCommitService(
        git_inspector=inspector
    )

    preparation_service = (
        PromotionPreparationService(
            execution_repository=(
                execution_repository
            ),
            preview_service=preview_service,
            promotion_repository=(
                promotion_repository
            ),
        )
    )

    finalization_service = (
        AuditedPromotionFinalizationService(
            promotion_repository=(
                promotion_repository
            ),
            preview_service=preview_service,
            workflow_service=workflow_service,
            validation_service=(
                validation_service
            ),
            commit_service=commit_service,
        )
    )

    return (
        preparation_service,
        finalization_service,
        promotion_repository,
    )


def test_completes_audited_promotion(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository_root = create_repository(
        tmp_path / "repository"
    )
    base_commit = run_git(
        repository_root,
        "rev-parse",
        "HEAD",
    )

    backend = FakeSandboxBackend(
        SandboxRunResult(
            exit_code=0,
            stdout_text="1 passed",
            stderr_text="",
            timed_out=False,
            duration_seconds=0.40,
        )
    )

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        (
            preparation_service,
            finalization_service,
            promotion_repository,
        ) = create_services(
            database=database,
            backend=backend,
        )

        prepared = preparation_service.prepare(
            execution_id=execution_id,
            target_repository_root=(
                repository_root
            ),
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:promocion:1"
            ),
            channel="telegram",
            test_target="tests",
        )

        assert (
            prepared.promotion.status
            == PromotionStatus
            .PENDING_CONFIRMATION
        )

        committed = (
            finalization_service.finalize(
                promotion_id=(
                    prepared.promotion.id
                ),
                confirmed_by_user_id=(
                    "123456"
                ),
                confirmation_message_id=(
                    "telegram:confirmacion:1"
                ),
                confirmation_channel=(
                    "telegram"
                ),
            )
        )

        assert (
            committed.status
            == PromotionStatus.COMMITTED
        )
        assert committed.commit_hash is not None
        assert committed.finished_at is not None
        assert committed.sandbox_exit_code == 0
        assert (
            committed.sandbox_timed_out
            is False
        )

        stored = (
            promotion_repository.get_by_id(
                committed.id
            )
        )

        assert stored == committed

    assert run_git(
        repository_root,
        "branch",
        "--show-current",
    ).startswith("promotion/")

    assert run_git(
        repository_root,
        "status",
        "--porcelain",
    ) == ""

    assert run_git(
        repository_root,
        "rev-parse",
        "HEAD^",
    ) == base_commit

    assert run_git(
        repository_root,
        "rev-parse",
        "main",
    ) == base_commit

    assert len(backend.requests) == 1


def test_audits_rollback_after_failed_tests(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository_root = create_repository(
        tmp_path / "repository"
    )
    base_commit = run_git(
        repository_root,
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

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        (
            preparation_service,
            finalization_service,
            promotion_repository,
        ) = create_services(
            database=database,
            backend=backend,
        )

        prepared = preparation_service.prepare(
            execution_id=execution_id,
            target_repository_root=(
                repository_root
            ),
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:promocion:1"
            ),
            channel="telegram",
            test_target="tests",
        )

        with pytest.raises(
            AuditedPromotionFinalizationError,
            match="no supero la validacion",
        ) as error_info:
            finalization_service.finalize(
                promotion_id=(
                    prepared.promotion.id
                ),
                confirmed_by_user_id=(
                    "123456"
                ),
                confirmation_message_id=(
                    "telegram:confirmacion:1"
                ),
                confirmation_channel=(
                    "telegram"
                ),
            )

        assert (
            error_info.value.sandbox_result
            is sandbox_result
        )

        stored = (
            promotion_repository.get_by_id(
                prepared.promotion.id
            )
        )

        assert stored is not None
        assert (
            stored.status
            == PromotionStatus.ROLLED_BACK
        )
        assert stored.sandbox_exit_code == 1
        assert (
            stored.error_message
            == (
                "Las pruebas de la promocion "
                "finalizaron con errores"
            )
        )

    assert run_git(
        repository_root,
        "branch",
        "--show-current",
    ) == "main"

    assert run_git(
        repository_root,
        "branch",
        "--list",
        "promotion/*",
    ) == ""

    assert run_git(
        repository_root,
        "rev-parse",
        "HEAD",
    ) == base_commit

    assert run_git(
        repository_root,
        "status",
        "--porcelain",
    ) == ""

    assert (
        repository_root / "suma.py"
    ).read_text(
        encoding="utf-8"
    ) == (
        "def sumar(a, b):\n"
        "    return a - b\n"
    )

    assert not (
        repository_root
        / "tests"
        / "test_suma.py"
    ).exists()