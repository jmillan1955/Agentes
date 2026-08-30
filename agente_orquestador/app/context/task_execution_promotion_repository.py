from __future__ import annotations

import sqlite3

from app.context.database import (
    ContextDatabase,
)
from app.execution.promotion_models import (
    PromotionPreview,
)
from app.execution.promotion_records import (
    PromotionStatus,
    TaskExecutionPromotion,
)


class TaskExecutionPromotionRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_by_id(
        self,
        promotion_id: int,
    ) -> TaskExecutionPromotion | None:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                status,
                workspace_path,
                repository_root,
                preview_hash,
                changed_file_count,
                added_file_count,
                modified_file_count,
                requested_by_user_id,
                request_message_id,
                channel,
                confirmed_by_user_id,
                confirmation_message_id,
                confirmation_channel,
                test_target,
                promotion_branch,
                base_commit,
                commit_hash,
                sandbox_exit_code,
                sandbox_timed_out,
                sandbox_duration_seconds,
                sandbox_stdout_text,
                sandbox_stderr_text,
                error_message,
                created_at,
                confirmed_at,
                finished_at
            FROM task_execution_promotions
            WHERE id = ?
            """,
            (promotion_id,),
        ).fetchone()

        return self._to_record(row)

    def get_latest_by_execution_id(
        self,
        execution_id: int,
    ) -> TaskExecutionPromotion | None:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser mayor "
                "que cero"
            )

        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                status,
                workspace_path,
                repository_root,
                preview_hash,
                changed_file_count,
                added_file_count,
                modified_file_count,
                requested_by_user_id,
                request_message_id,
                channel,
                confirmed_by_user_id,
                confirmation_message_id,
                confirmation_channel,
                test_target,
                promotion_branch,
                base_commit,
                commit_hash,
                sandbox_exit_code,
                sandbox_timed_out,
                sandbox_duration_seconds,
                sandbox_stdout_text,
                sandbox_stderr_text,
                error_message,
                created_at,
                confirmed_at,
                finished_at
            FROM task_execution_promotions
            WHERE execution_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (execution_id,),
        ).fetchone()

        return self._to_record(row)

    def create_pending(
        self,
        execution_id: int,
        preview: PromotionPreview,
        requested_by_user_id: str,
        request_message_id: str,
        channel: str,
        test_target: str,
    ) -> TaskExecutionPromotion:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser mayor "
                "que cero"
            )

        requested_by_user_id = (
            requested_by_user_id.strip()
        )
        request_message_id = (
            request_message_id.strip()
        )
        channel = channel.strip()
        test_target = test_target.strip()

        text_fields = {
            "requested_by_user_id": (
                requested_by_user_id
            ),
            "request_message_id": (
                request_message_id
            ),
            "channel": channel,
            "test_target": test_target,
        }

        for field_name, value in (
            text_fields.items()
        ):
            if not value:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

        if preview.changed_count <= 0:
            raise ValueError(
                "La vista previa no contiene "
                "cambios para promocionar"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution_row = connection.execute(
                """
                SELECT
                    status,
                    workspace_path
                FROM task_executions
                WHERE id = ?
                """,
                (execution_id,),
            ).fetchone()

            if execution_row is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            if (
                execution_row["status"]
                != "completed"
            ):
                raise ValueError(
                    "Solo puede promocionarse una "
                    "ejecucion completada"
                )

            if (
                execution_row["workspace_path"]
                != preview.workspace_path
            ):
                raise ValueError(
                    "El workspace no pertenece "
                    "a la ejecucion"
                )

            existing_row = connection.execute(
                """
                SELECT
                    id,
                    requested_by_user_id,
                    request_message_id,
                    channel,
                    test_target,
                    repository_root
                FROM task_execution_promotions
                WHERE execution_id = ?
                  AND preview_hash = ?
                """,
                (
                    execution_id,
                    preview.preview_hash,
                ),
            ).fetchone()

            if existing_row is not None:
                if (
                    existing_row[
                        "requested_by_user_id"
                    ]
                    == requested_by_user_id
                    and existing_row[
                        "request_message_id"
                    ]
                    == request_message_id
                    and existing_row["channel"]
                    == channel
                    and existing_row[
                        "test_target"
                    ]
                    == test_target
                    and existing_row[
                        "repository_root"
                    ]
                    == (
                        preview
                        .target_repository_root
                    )
                ):
                    connection.rollback()

                    existing = self.get_by_id(
                        existing_row["id"]
                    )

                    if existing is None:
                        raise RuntimeError(
                            "No se pudo recuperar "
                            "la promocion existente"
                        )

                    return existing

                raise ValueError(
                    "La vista previa ya fue "
                    "registrada con otra solicitud"
                )

            cursor = connection.execute(
                """
                INSERT INTO
                    task_execution_promotions (
                        execution_id,
                        status,
                        workspace_path,
                        repository_root,
                        preview_hash,
                        changed_file_count,
                        added_file_count,
                        modified_file_count,
                        requested_by_user_id,
                        request_message_id,
                        channel,
                        test_target
                    )
                VALUES (
                    ?,
                    'pending_confirmation',
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    execution_id,
                    preview.workspace_path,
                    (
                        preview
                        .target_repository_root
                    ),
                    preview.preview_hash,
                    preview.changed_count,
                    preview.added_count,
                    preview.modified_count,
                    requested_by_user_id,
                    request_message_id,
                    channel,
                    test_target,
                ),
            )

            promotion_id = int(
                cursor.lastrowid
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        created = self.get_by_id(
            promotion_id
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion creada"
            )

        return created

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskExecutionPromotion | None:
        if row is None:
            return None

        timed_out_value = row[
            "sandbox_timed_out"
        ]

        sandbox_timed_out = (
            None
            if timed_out_value is None
            else bool(timed_out_value)
        )

        return TaskExecutionPromotion(
            id=row["id"],
            execution_id=row["execution_id"],
            status=PromotionStatus(
                row["status"]
            ),
            workspace_path=(
                row["workspace_path"]
            ),
            repository_root=(
                row["repository_root"]
            ),
            preview_hash=row["preview_hash"],
            changed_file_count=(
                row["changed_file_count"]
            ),
            added_file_count=(
                row["added_file_count"]
            ),
            modified_file_count=(
                row["modified_file_count"]
            ),
            requested_by_user_id=(
                row["requested_by_user_id"]
            ),
            request_message_id=(
                row["request_message_id"]
            ),
            channel=row["channel"],
            confirmed_by_user_id=(
                row["confirmed_by_user_id"]
            ),
            confirmation_message_id=(
                row["confirmation_message_id"]
            ),
            confirmation_channel=(
                row["confirmation_channel"]
            ),
            test_target=row["test_target"],
            promotion_branch=(
                row["promotion_branch"]
            ),
            base_commit=row["base_commit"],
            commit_hash=row["commit_hash"],
            sandbox_exit_code=(
                row["sandbox_exit_code"]
            ),
            sandbox_timed_out=(
                sandbox_timed_out
            ),
            sandbox_duration_seconds=(
                row[
                    "sandbox_duration_seconds"
                ]
            ),
            sandbox_stdout_text=(
                row["sandbox_stdout_text"]
            ),
            sandbox_stderr_text=(
                row["sandbox_stderr_text"]
            ),
            error_message=(
                row["error_message"]
            ),
            created_at=row["created_at"],
            confirmed_at=(
                row["confirmed_at"]
            ),
            finished_at=row["finished_at"],
        )