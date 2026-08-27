from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.execution.models import (
    ExecutionStatus,
    TaskExecution,
)
from app.execution.state_machine import (
    ExecutionStateMachine,
)
from app.tasks import (
    TaskStateMachine,
    TaskStatus,
)

class TaskExecutionRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database
        self._state_machine = (
            ExecutionStateMachine()
        )
        self._task_state_machine = (
            TaskStateMachine()
        )

    def get_by_id(
        self,
        execution_id: int,
    ) -> TaskExecution | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                plan_id,
                approval_id,
                status,
                workspace_path,
                requested_by_user_id,
                request_message_id,
                channel,
                attempt_count,
                created_at,
                started_at,
                finished_at,
                last_error
            FROM task_executions
            WHERE id = ?
            """,
            (execution_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_task_id(
        self,
        task_id: int,
    ) -> TaskExecution | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                plan_id,
                approval_id,
                status,
                workspace_path,
                requested_by_user_id,
                request_message_id,
                channel,
                attempt_count,
                created_at,
                started_at,
                finished_at,
                last_error
            FROM task_executions
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        return self._to_record(row)

    def prepare(
        self,
        task_id: int,
        plan_id: int,
        approval_id: int,
        workspace_path: str,
        requested_by_user_id: str,
        request_message_id: str,
        channel: str,
    ) -> TaskExecution:
        identifiers = {
            "task_id": task_id,
            "plan_id": plan_id,
            "approval_id": approval_id,
        }

        for field_name, value in (
            identifiers.items()
        ):
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero"
                )

        workspace_path = workspace_path.strip()
        requested_by_user_id = (
            requested_by_user_id.strip()
        )
        request_message_id = (
            request_message_id.strip()
        )
        channel = channel.strip()

        text_fields = {
            "workspace_path": workspace_path,
            "requested_by_user_id": (
                requested_by_user_id
            ),
            "request_message_id": (
                request_message_id
            ),
            "channel": channel,
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

            existing = self.get_by_task_id(
                task_id
            )

            if existing is not None:
                if (
                    existing.plan_id == plan_id
                    and existing.approval_id
                    == approval_id
                    and existing.workspace_path
                    == workspace_path
                    and (
                        existing
                        .requested_by_user_id
                        == requested_by_user_id
                    )
                ):
                    connection.rollback()
                    return existing

                raise ValueError(
                    "La tarea ya tiene otra "
                    "ejecucion preparada"
                )

            row = connection.execute(
                """
                SELECT
                    tasks.status
                        AS task_status,
                    task_plans.task_id
                        AS plan_task_id,
                    task_plans.status
                        AS plan_status,
                    task_approvals.task_id
                        AS approval_task_id,
                    task_approvals.plan_id
                        AS approval_plan_id,
                    task_approvals
                        .authorized_user_id
                        AS authorized_user_id
                FROM tasks
                JOIN task_plans
                  ON task_plans.id = ?
                JOIN task_approvals
                  ON task_approvals.id = ?
                WHERE tasks.id = ?
                """,
                (
                    plan_id,
                    approval_id,
                    task_id,
                ),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea, el plan "
                    "o la autorizacion"
                )

            if row["task_status"] != "approved":
                raise ValueError(
                    "La tarea no esta aprobada"
                )

            if row["plan_task_id"] != task_id:
                raise ValueError(
                    "El plan no pertenece "
                    "a la tarea"
                )

            if row["plan_status"] != "approved":
                raise ValueError(
                    "El plan no esta aprobado"
                )

            if (
                row["approval_task_id"]
                != task_id
            ):
                raise ValueError(
                    "La autorizacion no pertenece "
                    "a la tarea"
                )

            if (
                row["approval_plan_id"]
                != plan_id
            ):
                raise ValueError(
                    "La autorizacion no pertenece "
                    "al plan"
                )

            if (
                row["authorized_user_id"]
                != requested_by_user_id
            ):
                raise ValueError(
                    "El usuario no esta autorizado "
                    "para preparar la ejecucion"
                )

            cursor = connection.execute(
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
                VALUES (
                    ?,
                    ?,
                    ?,
                    'prepared',
                    ?,
                    ?,
                    ?,
                    ?,
                    0
                )
                """,
                (
                    task_id,
                    plan_id,
                    approval_id,
                    workspace_path,
                    requested_by_user_id,
                    request_message_id,
                    channel,
                ),
            )

            execution_id = int(
                cursor.lastrowid
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        created = self.get_by_id(
            execution_id
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion preparada"
            )

        return created

    def start(
        self,
        execution_id: int,
    ) -> TaskExecution:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution = self.get_by_id(
                execution_id
            )

            if execution is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            self._state_machine.validate_transition(
                current_status=execution.status,
                target_status=(
                    ExecutionStatus.RUNNING
                ),
            )

            row = connection.execute(
                """
                SELECT status
                FROM tasks
                WHERE id = ?
                """,
                (execution.task_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea asociada"
                )

            task_status = TaskStatus(
                row["status"]
            )

            if (
                task_status
                == TaskStatus.APPROVED
            ):
                self._task_state_machine.validate_transition(
                    current_status=task_status,
                    target_status=(
                        TaskStatus.IN_PROGRESS
                    ),
                )

                task_cursor = connection.execute(
                    """
                    UPDATE tasks
                    SET
                        status = 'in_progress',
                        updated_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    WHERE id = ?
                      AND status = 'approved'
                    """,
                    (execution.task_id,),
                )

                if task_cursor.rowcount != 1:
                    raise RuntimeError(
                        "No se pudo iniciar "
                        "la tarea"
                    )

            elif (
                task_status
                != TaskStatus.IN_PROGRESS
            ):
                raise ValueError(
                    "La tarea no permite iniciar "
                    "la ejecucion"
                )

            execution_cursor = (
                connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = 'running',
                        attempt_count =
                            attempt_count + 1,
                        started_at = COALESCE(
                            started_at,
                            strftime(
                                '%Y-%m-%dT%H:%M:%fZ',
                                'now'
                            )
                        ),
                        finished_at = NULL,
                        last_error = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        execution.id,
                        execution.status.value,
                    ),
                )
            )

            if execution_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo iniciar "
                    "la ejecucion"
                )

            attempt_number = (
                execution.attempt_count + 1
            )

            connection.execute(
                """
                INSERT INTO
                    task_execution_attempts (
                        execution_id,
                        attempt_number,
                        status
                    )
                VALUES (?, ?, 'running')
                """,
                (
                    execution.id,
                    attempt_number,
                ),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        started = self.get_by_id(
            execution_id
        )

        if started is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion iniciada"
            )

        return started

    def complete(
        self,
        execution_id: int,
    ) -> TaskExecution:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution = self.get_by_id(
                execution_id
            )

            if execution is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            self._state_machine.validate_transition(
                current_status=execution.status,
                target_status=(
                    ExecutionStatus.COMPLETED
                ),
            )

            row = connection.execute(
                """
                SELECT status
                FROM tasks
                WHERE id = ?
                """,
                (execution.task_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea asociada"
                )

            task_status = TaskStatus(
                row["status"]
            )

            self._task_state_machine.validate_transition(
                current_status=task_status,
                target_status=(
                    TaskStatus.COMPLETED
                ),
            )

            task_cursor = connection.execute(
                """
                UPDATE tasks
                SET
                    status = 'completed',
                    completed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = 'in_progress'
                """,
                (execution.task_id,),
            )

            if task_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo completar "
                    "la tarea"
                )

            execution_cursor = (
                connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = 'completed',
                        finished_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        ),
                        last_error = NULL
                    WHERE id = ?
                      AND status = 'running'
                    """,
                    (execution.id,),
                )
            )

            if execution_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo completar "
                    "la ejecucion"
                )

            attempt_cursor = (
                connection.execute(
                    """
                    UPDATE
                        task_execution_attempts
                    SET
                        status = 'completed',
                        finished_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        ),
                        exit_code = 0,
                        error_message = NULL
                    WHERE execution_id = ?
                      AND attempt_number = ?
                      AND status = 'running'
                    """,
                    (
                        execution.id,
                        execution.attempt_count,
                    ),
                )
            )

            if attempt_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo completar "
                    "el intento actual"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        completed = self.get_by_id(
            execution_id
        )

        if completed is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion completada"
            )

        return completed

    def cancel(
        self,
        execution_id: int,
    ) -> TaskExecution:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution = self.get_by_id(
                execution_id
            )

            if execution is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            row = connection.execute(
                """
                SELECT status
                FROM tasks
                WHERE id = ?
                """,
                (execution.task_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea asociada"
                )

            task_status = TaskStatus(
                row["status"]
            )

            if (
                execution.status
                == ExecutionStatus.CANCELLED
                and task_status
                == TaskStatus.CANCELLED
            ):
                connection.rollback()
                return execution

            self._state_machine.validate_transition(
                current_status=execution.status,
                target_status=(
                    ExecutionStatus.CANCELLED
                ),
            )

            self._task_state_machine.validate_transition(
                current_status=task_status,
                target_status=(
                    TaskStatus.CANCELLED
                ),
            )

            task_cursor = connection.execute(
                """
                UPDATE tasks
                SET
                    status = 'cancelled',
                    completed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = ?
                """,
                (
                    execution.task_id,
                    task_status.value,
                ),
            )

            if task_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo cancelar "
                    "la tarea"
                )

            execution_cursor = (
                connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = 'cancelled',
                        finished_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        ),
                        last_error = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        execution.id,
                        execution.status.value,
                    ),
                )
            )

            if execution_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo cancelar "
                    "la ejecucion"
                )

            if (
                execution.status
                == ExecutionStatus.RUNNING
            ):
                attempt_cursor = (
                    connection.execute(
                        """
                        UPDATE
                            task_execution_attempts
                        SET
                            status = 'cancelled',
                            finished_at = strftime(
                                '%Y-%m-%dT%H:%M:%fZ',
                                'now'
                            ),
                            error_message = NULL
                        WHERE execution_id = ?
                          AND attempt_number = ?
                          AND status = 'running'
                        """,
                        (
                            execution.id,
                            execution.attempt_count,
                        ),
                    )
                )

                if attempt_cursor.rowcount != 1:
                    raise RuntimeError(
                        "No se pudo cancelar "
                        "el intento actual"
                    )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        cancelled = self.get_by_id(
            execution_id
        )

        if cancelled is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion cancelada"
            )

        return cancelled

    def finalize_failure(
        self,
        execution_id: int,
    ) -> TaskExecution:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution = self.get_by_id(
                execution_id
            )

            if execution is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            if execution.status not in {
                ExecutionStatus.FAILED,
                ExecutionStatus.INTERRUPTED,
            }:
                raise ValueError(
                    "Solo puede cerrarse "
                    "definitivamente una ejecucion "
                    "fallida o interrumpida"
                )

            row = connection.execute(
                """
                SELECT status
                FROM tasks
                WHERE id = ?
                """,
                (execution.task_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea asociada"
                )

            task_status = TaskStatus(
                row["status"]
            )

            if task_status == TaskStatus.FAILED:
                connection.rollback()
                return execution

            self._task_state_machine.validate_transition(
                current_status=task_status,
                target_status=TaskStatus.FAILED,
            )

            cursor = connection.execute(
                """
                UPDATE tasks
                SET
                    status = 'failed',
                    completed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = 'in_progress'
                """,
                (execution.task_id,),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo cerrar "
                    "la tarea fallida"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finalized = self.get_by_id(
            execution_id
        )

        if finalized is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion fallida"
            )

        return finalized

    def transition(
        self,
        execution_id: int,
        target_status: ExecutionStatus,
        last_error: str | None = None,
    ) -> TaskExecution:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        normalized_error = (
            last_error.strip()
            if last_error is not None
            else None
        )

        if target_status in {
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
        } and not normalized_error:
            raise ValueError(
                "Debe indicarse el error de "
                "la ejecucion"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current = self.get_by_id(
                execution_id
            )

            if current is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            self._state_machine.validate_transition(
                current_status=current.status,
                target_status=target_status,
            )

            if (
                target_status
                == ExecutionStatus.RUNNING
            ):
                cursor = connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = ?,
                        attempt_count =
                            attempt_count + 1,
                        started_at = COALESCE(
                            started_at,
                            strftime(
                                '%Y-%m-%dT%H:%M:%fZ',
                                'now'
                            )
                        ),
                        finished_at = NULL,
                        last_error = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        target_status.value,
                        execution_id,
                        current.status.value,
                    ),
                )

            elif target_status in {
                ExecutionStatus.FAILED,
                ExecutionStatus.INTERRUPTED,
            }:
                cursor = connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = ?,
                        finished_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        ),
                        last_error = ?
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        target_status.value,
                        normalized_error,
                        execution_id,
                        current.status.value,
                    ),
                )

            else:
                cursor = connection.execute(
                    """
                    UPDATE task_executions
                    SET
                        status = ?,
                        finished_at = strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        ),
                        last_error = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        target_status.value,
                        execution_id,
                        current.status.value,
                    ),
                )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo actualizar "
                    "la ejecucion"
                )
            if (
                current.status
                == ExecutionStatus.RUNNING
            ):
                attempt_cursor = (
                    connection.execute(
                        """
                        UPDATE
                            task_execution_attempts
                        SET
                            status = ?,
                            finished_at = strftime(
                                '%Y-%m-%dT%H:%M:%fZ',
                                'now'
                            ),
                            error_message = ?
                        WHERE execution_id = ?
                          AND attempt_number = ?
                          AND status = 'running'
                        """,
                        (
                            target_status.value,
                            normalized_error,
                            current.id,
                            current.attempt_count,
                        ),
                    )
                )

                if attempt_cursor.rowcount != 1:
                    raise RuntimeError(
                        "No se pudo cerrar "
                        "el intento actual"
                    )
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        updated = self.get_by_id(
            execution_id
        )

        if updated is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la ejecucion actualizada"
            )

        return updated

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskExecution | None:
        if row is None:
            return None

        return TaskExecution(
            id=row["id"],
            task_id=row["task_id"],
            plan_id=row["plan_id"],
            approval_id=row["approval_id"],
            status=ExecutionStatus(
                row["status"]
            ),
            workspace_path=(
                row["workspace_path"]
            ),
            requested_by_user_id=(
                row["requested_by_user_id"]
            ),
            request_message_id=(
                row["request_message_id"]
            ),
            channel=row["channel"],
            attempt_count=row["attempt_count"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_error=row["last_error"],
        )