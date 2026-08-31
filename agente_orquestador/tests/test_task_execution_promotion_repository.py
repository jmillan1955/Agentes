from pathlib import Path

import pytest

from app.context.database import (
    ContextDatabase,
)
from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.execution.promotion_models import (
    PromotionChangeType,
    PromotionFileChange,
    PromotionPreview,
)
from app.execution.promotion_records import (
    PromotionStatus,
)
from app.execution.sandbox import (
    SandboxRunResult,
)
from app.execution.promotion_commit import (
    PromotionCommitResult,
)

def prepare_completed_execution(
    database: ContextDatabase,
    workspace_path: Path,
    execution_status: str = "completed",
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
            execution_status,
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


def create_preview(
    workspace_path: Path,
    repository_root: Path,
    preview_hash: str = "a" * 64,
) -> PromotionPreview:
    return PromotionPreview(
        workspace_path=str(workspace_path),
        target_repository_root=(
            str(repository_root)
        ),
        changes=(
            PromotionFileChange(
                relative_path="suma.py",
                change_type=(
                    PromotionChangeType
                    .MODIFIED
                ),
                previous_sha256="b" * 64,
                current_sha256="c" * 64,
                previous_size_bytes=20,
                current_size_bytes=21,
                diff_text="diff suma",
            ),
            PromotionFileChange(
                relative_path=(
                    "tests/test_suma.py"
                ),
                change_type=(
                    PromotionChangeType.ADDED
                ),
                previous_sha256=None,
                current_sha256="d" * 64,
                previous_size_bytes=None,
                current_size_bytes=50,
                diff_text="diff prueba",
            ),
        ),
        preview_hash=preview_hash,
    )


def create_pending(
    repository: (
        TaskExecutionPromotionRepository
    ),
    execution_id: int,
    preview: PromotionPreview,
    request_message_id: str = (
        "telegram:promocion:1"
    ),
):
    return repository.create_pending(
        execution_id=execution_id,
        preview=preview,
        requested_by_user_id="123456",
        request_message_id=(
            request_message_id
        ),
        channel="telegram",
        test_target="tests",
    )


def test_initializes_promotion_schema(
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        version = (
            database.connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )

        table = (
            database.connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name =
                    'task_execution_promotions'
                """
            ).fetchone()
        )

        assert version == 10
        assert table is not None


def test_creates_pending_promotion(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    repository_root = (
        tmp_path / "repository"
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

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        preview = create_preview(
            workspace_path=workspace,
            repository_root=(
                repository_root
            ),
        )

        promotion = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=preview,
        )

        assert promotion.id > 0
        assert (
            promotion.execution_id
            == execution_id
        )
        assert (
            promotion.status
            == PromotionStatus
            .PENDING_CONFIRMATION
        )
        assert (
            promotion.workspace_path
            == str(workspace)
        )
        assert (
            promotion.repository_root
            == str(repository_root)
        )
        assert (
            promotion.preview_hash
            == preview.preview_hash
        )
        assert (
            promotion.changed_file_count
            == 2
        )
        assert (
            promotion.added_file_count
            == 1
        )
        assert (
            promotion.modified_file_count
            == 1
        )
        assert (
            promotion.requested_by_user_id
            == "123456"
        )
        assert (
            promotion.test_target
            == "tests"
        )
        assert (
            promotion.confirmed_by_user_id
            is None
        )
        assert promotion.commit_hash is None


def test_gets_promotion_by_id(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        created = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        loaded = repository.get_by_id(
            created.id
        )

        assert loaded == created
        assert (
            repository.get_by_id(999)
            is None
        )


def test_repeats_same_request_idempotently(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        preview = create_preview(
            workspace_path=workspace,
            repository_root=(
                tmp_path / "repository"
            ),
        )

        first = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=preview,
        )
        second = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=preview,
        )

        assert second == first

        count = (
            database.connection.execute(
                """
                SELECT COUNT(*)
                FROM task_execution_promotions
                """
            ).fetchone()[0]
        )

        assert count == 1


def test_rejects_same_preview_from_other_request(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        preview = create_preview(
            workspace_path=workspace,
            repository_root=(
                tmp_path / "repository"
            ),
        )

        create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=preview,
        )

        with pytest.raises(
            ValueError,
            match="otra solicitud",
        ):
            create_pending(
                repository=repository,
                execution_id=execution_id,
                preview=preview,
                request_message_id=(
                    "telegram:promocion:2"
                ),
            )


def test_rejects_non_completed_execution(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
                execution_status="failed",
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match="ejecucion completada",
        ):
            create_pending(
                repository=repository,
                execution_id=execution_id,
                preview=create_preview(
                    workspace_path=workspace,
                    repository_root=(
                        tmp_path / "repository"
                    ),
                ),
            )


def test_rejects_other_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match="no pertenece",
        ):
            create_pending(
                repository=repository,
                execution_id=execution_id,
                preview=create_preview(
                    workspace_path=(
                        tmp_path
                        / "otro-workspace"
                    ),
                    repository_root=(
                        tmp_path / "repository"
                    ),
                ),
            )


def test_gets_latest_promotion(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        first = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
                preview_hash="a" * 64,
            ),
            request_message_id=(
                "telegram:promocion:1"
            ),
        )

        second = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
                preview_hash="e" * 64,
            ),
            request_message_id=(
                "telegram:promocion:2"
            ),
        )

        latest = (
            repository
            .get_latest_by_execution_id(
                execution_id
            )
        )

        assert first.id < second.id
        assert latest == second

def test_confirms_pending_promotion(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        pending = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        confirmed = repository.confirm(
            promotion_id=pending.id,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
        )

        assert (
            confirmed.status
            == PromotionStatus.CONFIRMED
        )
        assert (
            confirmed.confirmed_by_user_id
            == "123456"
        )
        assert (
            confirmed.confirmation_message_id
            == "telegram:confirmacion:1"
        )
        assert (
            confirmed.confirmation_channel
            == "telegram"
        )
        assert confirmed.confirmed_at is not None
        assert confirmed.finished_at is None


def test_repeats_confirmation_idempotently(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        pending = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        first = repository.confirm(
            promotion_id=pending.id,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
        )

        second = repository.confirm(
            promotion_id=pending.id,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
        )

        assert second == first


def test_rejects_different_confirmation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        pending = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        repository.confirm(
            promotion_id=pending.id,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
        )

        with pytest.raises(
            ValueError,
            match="de otra forma",
        ):
            repository.confirm(
                promotion_id=pending.id,
                confirmed_by_user_id="999999",
                confirmation_message_id=(
                    "telegram:confirmacion:2"
                ),
                confirmation_channel=(
                    "telegram"
                ),
            )

def create_confirmed_promotion(
    database: ContextDatabase,
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"

    execution_id = (
        prepare_completed_execution(
            database=database,
            workspace_path=workspace,
        )
    )

    repository = (
        TaskExecutionPromotionRepository(
            database
        )
    )

    pending = create_pending(
        repository=repository,
        execution_id=execution_id,
        preview=create_preview(
            workspace_path=workspace,
            repository_root=(
                tmp_path / "repository"
            ),
        ),
    )

    confirmed = repository.confirm(
        promotion_id=pending.id,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
    )

    return repository, confirmed

def test_marks_confirmed_promotion_as_applied(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, confirmed = (
            create_confirmed_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        applied = repository.mark_applied(
            promotion_id=confirmed.id,
            promotion_branch=(
                "promotion/execution-7"
            ),
            base_commit="b" * 40,
        )

        assert (
            applied.status
            == PromotionStatus.APPLIED
        )
        assert (
            applied.promotion_branch
            == "promotion/execution-7"
        )
        assert applied.base_commit == "b" * 40
        assert applied.commit_hash is None


def test_repeats_applied_transition_idempotently(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, confirmed = (
            create_confirmed_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        first = repository.mark_applied(
            promotion_id=confirmed.id,
            promotion_branch=(
                "promotion/execution-7"
            ),
            base_commit="b" * 40,
        )

        second = repository.mark_applied(
            promotion_id=confirmed.id,
            promotion_branch=(
                "promotion/execution-7"
            ),
            base_commit="b" * 40,
        )

        assert second == first


def test_rejects_applied_before_confirmation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        pending = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        with pytest.raises(
            ValueError,
            match="No se permite",
        ):
            repository.mark_applied(
                promotion_id=pending.id,
                promotion_branch=(
                    "promotion/execution-7"
                ),
                base_commit="b" * 40,
            )

def create_applied_promotion(
    database: ContextDatabase,
    tmp_path: Path,
):
    repository, confirmed = (
        create_confirmed_promotion(
            database=database,
            tmp_path=tmp_path,
        )
    )

    applied = repository.mark_applied(
        promotion_id=confirmed.id,
        promotion_branch=(
            "promotion/execution-7"
        ),
        base_commit="b" * 40,
    )

    return repository, applied


def create_successful_sandbox_result(
) -> SandboxRunResult:
    return SandboxRunResult(
        exit_code=0,
        stdout_text="1 passed",
        stderr_text="",
        timed_out=False,
        duration_seconds=0.25,
    )


def test_marks_applied_promotion_as_validated(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        sandbox_result = (
            create_successful_sandbox_result()
        )

        validated = repository.mark_validated(
            promotion_id=applied.id,
            sandbox_result=sandbox_result,
        )

        assert (
            validated.status
            == PromotionStatus.VALIDATED
        )
        assert validated.sandbox_exit_code == 0
        assert (
            validated.sandbox_timed_out
            is False
        )
        assert (
            validated
            .sandbox_duration_seconds
            == 0.25
        )
        assert (
            validated.sandbox_stdout_text
            == "1 passed"
        )
        assert (
            validated.sandbox_stderr_text
            is None
        )


def test_repeats_validation_idempotently(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        sandbox_result = (
            create_successful_sandbox_result()
        )

        first = repository.mark_validated(
            promotion_id=applied.id,
            sandbox_result=sandbox_result,
        )

        second = repository.mark_validated(
            promotion_id=applied.id,
            sandbox_result=sandbox_result,
        )

        assert second == first


def test_rejects_failed_sandbox_validation(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        failed_result = SandboxRunResult(
            exit_code=1,
            stdout_text="1 failed",
            stderr_text="AssertionError",
            timed_out=False,
            duration_seconds=0.30,
        )

        with pytest.raises(
            ValueError,
            match="pruebas satisfactorias",
        ):
            repository.mark_validated(
                promotion_id=applied.id,
                sandbox_result=failed_result,
            )

def create_validated_promotion(
    database: ContextDatabase,
    tmp_path: Path,
):
    repository, applied = (
        create_applied_promotion(
            database=database,
            tmp_path=tmp_path,
        )
    )

    validated = repository.mark_validated(
        promotion_id=applied.id,
        sandbox_result=(
            create_successful_sandbox_result()
        ),
    )

    return repository, validated


def create_commit_result(
    repository_root: Path,
) -> PromotionCommitResult:
    return PromotionCommitResult(
        repository_root=(
            repository_root.resolve()
        ),
        branch_name=(
            "promotion/execution-7"
        ),
        base_commit="b" * 40,
        commit_hash="c" * 40,
        commit_message=(
            "Promocionar ejecucion #7"
        ),
        committed_paths=(
            "suma.py",
            "tests/test_suma.py",
        ),
    )


def test_marks_validated_promotion_as_committed(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, validated = (
            create_validated_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        commit_result = create_commit_result(
            tmp_path / "repository"
        )

        committed = repository.mark_committed(
            promotion_id=validated.id,
            commit_result=commit_result,
        )

        assert (
            committed.status
            == PromotionStatus.COMMITTED
        )
        assert committed.commit_hash == "c" * 40
        assert committed.finished_at is not None
        assert committed.error_message is None


def test_repeats_committed_transition_idempotently(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, validated = (
            create_validated_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        commit_result = create_commit_result(
            tmp_path / "repository"
        )

        first = repository.mark_committed(
            promotion_id=validated.id,
            commit_result=commit_result,
        )

        second = repository.mark_committed(
            promotion_id=validated.id,
            commit_result=commit_result,
        )

        assert second == first


def test_rejects_commit_from_other_branch(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, validated = (
            create_validated_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        commit_result = PromotionCommitResult(
            repository_root=(
                tmp_path
                / "repository"
            ).resolve(),
            branch_name=(
                "promotion/otra-ejecucion"
            ),
            base_commit="b" * 40,
            commit_hash="c" * 40,
            commit_message=(
                "Promocionar ejecucion #7"
            ),
            committed_paths=(
                "suma.py",
            ),
        )

        with pytest.raises(
            ValueError,
            match="no pertenece",
        ):
            repository.mark_committed(
                promotion_id=validated.id,
                commit_result=commit_result,
            )

def test_marks_pending_promotion_as_failed(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_id = (
            prepare_completed_execution(
                database=database,
                workspace_path=workspace,
            )
        )

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        pending = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=create_preview(
                workspace_path=workspace,
                repository_root=(
                    tmp_path / "repository"
                ),
            ),
        )

        failed = repository.mark_failed(
            promotion_id=pending.id,
            error_message=(
                "La vista previa ha caducado"
            ),
        )

        assert (
            failed.status
            == PromotionStatus.FAILED
        )
        assert (
            failed.error_message
            == "La vista previa ha caducado"
        )
        assert failed.finished_at is not None
        assert (
            failed.confirmed_by_user_id
            is None
        )


def test_preserves_failed_sandbox_diagnostic(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        sandbox_result = SandboxRunResult(
            exit_code=1,
            stdout_text="1 failed",
            stderr_text="AssertionError",
            timed_out=False,
            duration_seconds=0.30,
        )

        failed = repository.mark_failed(
            promotion_id=applied.id,
            error_message=(
                "Las pruebas fallaron"
            ),
            sandbox_result=sandbox_result,
        )

        assert (
            failed.status
            == PromotionStatus.FAILED
        )
        assert failed.sandbox_exit_code == 1
        assert (
            failed.sandbox_timed_out
            is False
        )
        assert (
            failed.sandbox_stdout_text
            == "1 failed"
        )
        assert (
            failed.sandbox_stderr_text
            == "AssertionError"
        )


def test_marks_failed_promotion_as_rolled_back(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        failed = repository.mark_failed(
            promotion_id=applied.id,
            error_message=(
                "Las pruebas fallaron"
            ),
        )

        rolled_back = (
            repository.mark_rolled_back(
                promotion_id=failed.id
            )
        )

        assert (
            rolled_back.status
            == PromotionStatus.ROLLED_BACK
        )
        assert (
            rolled_back.error_message
            == "Las pruebas fallaron"
        )
        assert rolled_back.finished_at is not None


def test_repeats_rollback_idempotently(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, applied = (
            create_applied_promotion(
                database=database,
                tmp_path=tmp_path,
            )
        )

        failed = repository.mark_failed(
            promotion_id=applied.id,
            error_message=(
                "Las pruebas fallaron"
            ),
        )

        first = repository.mark_rolled_back(
            promotion_id=failed.id
        )
        second = repository.mark_rolled_back(
            promotion_id=failed.id
        )

        assert second == first

def test_persists_target_subdirectory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    repository_root = (
        tmp_path / "repository"
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

        repository = (
            TaskExecutionPromotionRepository(
                database
            )
        )

        preview = PromotionPreview(
            workspace_path=str(workspace),
            target_repository_root=(
                str(repository_root)
            ),
            target_subdirectory=(
                "puntuacion_padel"
            ),
            changes=(
                PromotionFileChange(
                    relative_path=(
                        "puntuacion_padel/"
                        "suma.py"
                    ),
                    change_type=(
                        PromotionChangeType.ADDED
                    ),
                    previous_sha256=None,
                    current_sha256="a" * 64,
                    previous_size_bytes=None,
                    current_size_bytes=20,
                    diff_text="diff suma",
                ),
            ),
            preview_hash="b" * 64,
        )

        created = create_pending(
            repository=repository,
            execution_id=execution_id,
            preview=preview,
            request_message_id=(
                "telegram:promocion:"
                "subdirectorio"
            ),
        )

        loaded = repository.get_by_id(
            created.id
        )

        assert loaded is not None
        assert (
            loaded.target_subdirectory
            == "puntuacion_padel"
        )

        latest = (
            repository
            .get_latest_by_execution_id(
                execution_id
            )
        )

        assert latest is not None
        assert (
            latest.target_subdirectory
            == "puntuacion_padel"
        )