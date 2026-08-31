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
from app.execution.promotion_state_machine import (
    PromotionStateMachine,
)
from app.execution.sandbox import (
    SandboxRunResult,
)
from app.execution.promotion_commit import (
    PromotionCommitResult,
)

class TaskExecutionPromotionRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database
        self._state_machine = (
            PromotionStateMachine()
        )

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
                target_subdirectory,
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
                target_subdirectory,
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
                    repository_root,
                    target_subdirectory
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
                    and existing_row[
                        "target_subdirectory"
                    ]
                    == (
                        preview
                        .target_subdirectory
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
                        target_subdirectory,
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
                    (
                        preview
                        .target_subdirectory
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

    def confirm(
        self,
        promotion_id: int,
        confirmed_by_user_id: str,
        confirmation_message_id: str,
        confirmation_channel: str,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        confirmed_by_user_id = (
            confirmed_by_user_id.strip()
        )
        confirmation_message_id = (
            confirmation_message_id.strip()
        )
        confirmation_channel = (
            confirmation_channel.strip()
        )

        text_fields = {
            "confirmed_by_user_id": (
                confirmed_by_user_id
            ),
            "confirmation_message_id": (
                confirmation_message_id
            ),
            "confirmation_channel": (
                confirmation_channel
            ),
        }

        for field_name, value in (
            text_fields.items()
        ):
            if not value:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            if (
                current.status
                != PromotionStatus
                .PENDING_CONFIRMATION
            ):
                if (
                    current.confirmed_by_user_id
                    == confirmed_by_user_id
                    and current
                    .confirmation_message_id
                    == confirmation_message_id
                    and current
                    .confirmation_channel
                    == confirmation_channel
                    and current.confirmed_at
                    is not None
                ):
                    connection.rollback()
                    return current

                raise ValueError(
                    "La promocion ya fue "
                    "confirmada de otra forma"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.CONFIRMED
                ),
            )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'confirmed',
                    confirmed_by_user_id = ?,
                    confirmation_message_id = ?,
                    confirmation_channel = ?,
                    confirmed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    error_message = NULL,
                    finished_at = NULL
                WHERE id = ?
                  AND status =
                    'pending_confirmation'
                """,
                (
                    confirmed_by_user_id,
                    confirmation_message_id,
                    confirmation_channel,
                    promotion_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo confirmar la "
                    "promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        confirmed = self.get_by_id(
            promotion_id
        )

        if confirmed is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion confirmada"
            )

        return confirmed

    def mark_applied(
        self,
        promotion_id: int,
        promotion_branch: str,
        base_commit: str,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        promotion_branch = (
            promotion_branch.strip()
        )
        base_commit = (
            base_commit.strip().lower()
        )

        if (
            not promotion_branch
            or not promotion_branch.startswith(
                "promotion/"
            )
        ):
            raise ValueError(
                "promotion_branch debe comenzar "
                "por promotion/"
            )

        if (
            len(base_commit) != 40
            or any(
                character
                not in "0123456789abcdef"
                for character in base_commit
            )
        ):
            raise ValueError(
                "base_commit debe ser un hash "
                "Git valido"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            if current.status in {
                PromotionStatus.APPLIED,
                PromotionStatus.VALIDATED,
                PromotionStatus.COMMITTED,
            }:
                if (
                    current.promotion_branch
                    == promotion_branch
                    and current.base_commit
                    == base_commit
                ):
                    connection.rollback()
                    return current

                raise ValueError(
                    "La promocion fue aplicada "
                    "con otra rama o commit base"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.APPLIED
                ),
            )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'applied',
                    promotion_branch = ?,
                    base_commit = ?,
                    commit_hash = NULL,
                    sandbox_exit_code = NULL,
                    sandbox_timed_out = NULL,
                    sandbox_duration_seconds = NULL,
                    sandbox_stdout_text = NULL,
                    sandbox_stderr_text = NULL,
                    error_message = NULL,
                    finished_at = NULL
                WHERE id = ?
                  AND status = 'confirmed'
                """,
                (
                    promotion_branch,
                    base_commit,
                    promotion_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar la "
                    "aplicacion de la promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        applied = self.get_by_id(
            promotion_id
        )

        if applied is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion aplicada"
            )

        return applied

    def mark_validated(
        self,
        promotion_id: int,
        sandbox_result: SandboxRunResult,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        if (
            sandbox_result.timed_out
            or sandbox_result.exit_code != 0
        ):
            raise ValueError(
                "Solo puede validarse una "
                "promocion con pruebas "
                "satisfactorias"
            )

        stdout_text = (
            sandbox_result.stdout_text.strip()
            or None
        )
        stderr_text = (
            sandbox_result.stderr_text.strip()
            or None
        )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            if current.status in {
                PromotionStatus.VALIDATED,
                PromotionStatus.COMMITTED,
            }:
                if (
                    current.sandbox_exit_code
                    == sandbox_result.exit_code
                    and current.sandbox_timed_out
                    == sandbox_result.timed_out
                    and current
                    .sandbox_duration_seconds
                    == (
                        sandbox_result
                        .duration_seconds
                    )
                    and current
                    .sandbox_stdout_text
                    == stdout_text
                    and current
                    .sandbox_stderr_text
                    == stderr_text
                ):
                    connection.rollback()
                    return current

                raise ValueError(
                    "La promocion fue validada "
                    "con otro resultado"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.VALIDATED
                ),
            )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'validated',
                    sandbox_exit_code = ?,
                    sandbox_timed_out = ?,
                    sandbox_duration_seconds = ?,
                    sandbox_stdout_text = ?,
                    sandbox_stderr_text = ?,
                    error_message = NULL,
                    finished_at = NULL
                WHERE id = ?
                  AND status = 'applied'
                """,
                (
                    sandbox_result.exit_code,
                    int(
                        sandbox_result.timed_out
                    ),
                    (
                        sandbox_result
                        .duration_seconds
                    ),
                    stdout_text,
                    stderr_text,
                    promotion_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar la "
                    "validacion de la promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        validated = self.get_by_id(
            promotion_id
        )

        if validated is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion validada"
            )

        return validated

    def mark_committed(
        self,
        promotion_id: int,
        commit_result: PromotionCommitResult,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            if (
                current.status
                == PromotionStatus.COMMITTED
            ):
                if (
                    current.commit_hash
                    == commit_result.commit_hash
                    and current.promotion_branch
                    == commit_result.branch_name
                    and current.base_commit
                    == commit_result.base_commit
                ):
                    connection.rollback()
                    return current

                raise ValueError(
                    "La promocion fue confirmada "
                    "con otro commit"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.COMMITTED
                ),
            )

            if (
                current.repository_root
                != str(
                    commit_result
                    .repository_root
                )
                or current.promotion_branch
                != commit_result.branch_name
                or current.base_commit
                != commit_result.base_commit
            ):
                raise ValueError(
                    "El resultado del commit no "
                    "pertenece a la promocion"
                )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'committed',
                    commit_hash = ?,
                    error_message = NULL,
                    finished_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = 'validated'
                """,
                (
                    commit_result.commit_hash,
                    promotion_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar el "
                    "commit de promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        committed = self.get_by_id(
            promotion_id
        )

        if committed is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion confirmada en Git"
            )

        return committed

    def mark_failed(
        self,
        promotion_id: int,
        error_message: str,
        sandbox_result: (
            SandboxRunResult | None
        ) = None,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        error_message = error_message.strip()

        if not error_message:
            raise ValueError(
                "error_message no puede estar "
                "vacio"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            exit_code = (
                sandbox_result.exit_code
                if sandbox_result is not None
                else current.sandbox_exit_code
            )
            timed_out = (
                sandbox_result.timed_out
                if sandbox_result is not None
                else current.sandbox_timed_out
            )
            duration_seconds = (
                sandbox_result.duration_seconds
                if sandbox_result is not None
                else (
                    current
                    .sandbox_duration_seconds
                )
            )

            if sandbox_result is not None:
                stdout_text = (
                    sandbox_result
                    .stdout_text
                    .strip()
                    or None
                )
                stderr_text = (
                    sandbox_result
                    .stderr_text
                    .strip()
                    or None
                )
            else:
                stdout_text = (
                    current.sandbox_stdout_text
                )
                stderr_text = (
                    current.sandbox_stderr_text
                )

            if (
                current.status
                == PromotionStatus.FAILED
            ):
                if (
                    current.error_message
                    == error_message
                    and current
                    .sandbox_exit_code
                    == exit_code
                    and current
                    .sandbox_timed_out
                    == timed_out
                    and current
                    .sandbox_duration_seconds
                    == duration_seconds
                    and current
                    .sandbox_stdout_text
                    == stdout_text
                    and current
                    .sandbox_stderr_text
                    == stderr_text
                ):
                    connection.rollback()
                    return current

                raise ValueError(
                    "La promocion ya registro "
                    "otro fallo"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.FAILED
                ),
            )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'failed',
                    sandbox_exit_code = ?,
                    sandbox_timed_out = ?,
                    sandbox_duration_seconds = ?,
                    sandbox_stdout_text = ?,
                    sandbox_stderr_text = ?,
                    error_message = ?,
                    finished_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = ?
                """,
                (
                    exit_code,
                    (
                        None
                        if timed_out is None
                        else int(timed_out)
                    ),
                    duration_seconds,
                    stdout_text,
                    stderr_text,
                    error_message,
                    promotion_id,
                    current.status.value,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar el "
                    "fallo de la promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        failed = self.get_by_id(
            promotion_id
        )

        if failed is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion fallida"
            )

        return failed

    def mark_rolled_back(
        self,
        promotion_id: int,
    ) -> TaskExecutionPromotion:
        if promotion_id <= 0:
            raise ValueError(
                "promotion_id debe ser mayor "
                "que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                promotion_id
            )

            if current is None:
                raise ValueError(
                    "No existe la promocion"
                )

            if (
                current.status
                == PromotionStatus.ROLLED_BACK
            ):
                connection.rollback()
                return current

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=(
                    PromotionStatus.ROLLED_BACK
                ),
            )

            cursor = connection.execute(
                """
                UPDATE task_execution_promotions
                SET
                    status = 'rolled_back',
                    finished_at = COALESCE(
                        finished_at,
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    )
                WHERE id = ?
                  AND status = ?
                """,
                (
                    promotion_id,
                    current.status.value,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar el "
                    "rollback de la promocion"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        rolled_back = self.get_by_id(
            promotion_id
        )

        if rolled_back is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "promocion revertida"
            )

        return rolled_back

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
            target_subdirectory=(
                row["target_subdirectory"]
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