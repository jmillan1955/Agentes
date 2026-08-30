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

        assert version == 9
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