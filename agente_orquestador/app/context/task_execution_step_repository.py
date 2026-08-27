from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.execution.models import (
    ExecutionStep,
    ExecutionStepStatus,
)
from app.execution.state_machine import (
    ExecutionStepStateMachine,
)
from app.execution.state_machine import (
    ExecutionStepStateMachine,
)

class TaskExecutionStepRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database
        self._state_machine = (
            ExecutionStepStateMachine()
        )

    def get_by_id(
        self,
        step_id: int,
    ) -> ExecutionStep | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                attempt_id,
                step_number,
                name,
                action_type,
                status,
                started_at,
                finished_at,
                exit_code,
                stdout_text,
                stderr_text,
                error_message
            FROM task_execution_steps
            WHERE id = ?
            """,
            (step_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_number(
        self,
        attempt_id: int,
        step_number: int,
    ) -> ExecutionStep | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                attempt_id,
                step_number,
                name,
                action_type,
                status,
                started_at,
                finished_at,
                exit_code,
                stdout_text,
                stderr_text,
                error_message
            FROM task_execution_steps
            WHERE attempt_id = ?
              AND step_number = ?
            """,
            (
                attempt_id,
                step_number,
            ),
        ).fetchone()

        return self._to_record(row)

    def list_by_attempt(
        self,
        attempt_id: int,
    ) -> tuple[ExecutionStep, ...]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                attempt_id,
                step_number,
                name,
                action_type,
                status,
                started_at,
                finished_at,
                exit_code,
                stdout_text,
                stderr_text,
                error_message
            FROM task_execution_steps
            WHERE attempt_id = ?
            ORDER BY step_number
            """,
            (attempt_id,),
        ).fetchall()

        return tuple(
            self._to_record_required(row)
            for row in rows
        )

    def create(
        self,
        attempt_id: int,
        step_number: int,
        name: str,
        action_type: str,
    ) -> ExecutionStep:
        if attempt_id <= 0:
            raise ValueError(
                "attempt_id debe ser "
                "mayor que cero"
            )

        if step_number <= 0:
            raise ValueError(
                "step_number debe ser "
                "mayor que cero"
            )

        name = name.strip()
        action_type = action_type.strip()

        if not name:
            raise ValueError(
                "name no puede estar vacio"
            )

        if not action_type:
            raise ValueError(
                "action_type no puede "
                "estar vacio"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            existing = self.get_by_number(
                attempt_id=attempt_id,
                step_number=step_number,
            )

            if existing is not None:
                if (
                    existing.name == name
                    and existing.action_type
                    == action_type
                ):
                    connection.rollback()
                    return existing

                raise ValueError(
                    "El numero de paso ya existe "
                    "con otro contenido"
                )

            attempt_row = connection.execute(
                """
                SELECT status
                FROM task_execution_attempts
                WHERE id = ?
                """,
                (attempt_id,),
            ).fetchone()

            if attempt_row is None:
                raise ValueError(
                    "No existe el intento"
                )

            if (
                attempt_row["status"]
                != "running"
            ):
                raise ValueError(
                    "Solo se pueden crear pasos "
                    "en un intento activo"
                )

            cursor = connection.execute(
                """
                INSERT INTO task_execution_steps (
                    attempt_id,
                    step_number,
                    name,
                    action_type,
                    status
                )
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (
                    attempt_id,
                    step_number,
                    name,
                    action_type,
                ),
            )

            step_id = int(
                cursor.lastrowid
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        created = self.get_by_id(
            step_id
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el paso creado"
            )

        return created

    def start(
        self,
        step_id: int,
    ) -> ExecutionStep:
        if step_id <= 0:
            raise ValueError(
                "step_id debe ser mayor "
                "que cero"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            step = self.get_by_id(
                step_id
            )

            if step is None:
                raise ValueError(
                    "No existe el paso"
                )

            self._state_machine.validate_transition(
                current_status=step.status,
                target_status=(
                    ExecutionStepStatus.RUNNING
                ),
            )

            attempt_row = connection.execute(
                """
                SELECT status
                FROM task_execution_attempts
                WHERE id = ?
                """,
                (step.attempt_id,),
            ).fetchone()

            if (
                attempt_row is None
                or attempt_row["status"]
                != "running"
            ):
                raise ValueError(
                    "El intento no esta activo"
                )

            cursor = connection.execute(
                """
                UPDATE task_execution_steps
                SET
                    status = 'running',
                    started_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = 'pending'
                """,
                (step.id,),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo iniciar el paso"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        started = self.get_by_id(
            step_id
        )

        if started is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el paso iniciado"
            )

        return started

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> ExecutionStep | None:
        if row is None:
            return None

        return (
            TaskExecutionStepRepository
            ._to_record_required(row)
        )

    def complete(
        self,
        step_id: int,
        stdout_text: str | None = None,
        stderr_text: str | None = None,
    ) -> ExecutionStep:
        if step_id <= 0:
            raise ValueError(
                "step_id debe ser mayor "
                "que cero"
            )

        stdout_text = (
            stdout_text.strip()
            if stdout_text is not None
            else None
        )
        stderr_text = (
            stderr_text.strip()
            if stderr_text is not None
            else None
        )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            step = self.get_by_id(
                step_id
            )

            if step is None:
                raise ValueError(
                    "No existe el paso"
                )

            self._state_machine.validate_transition(
                current_status=step.status,
                target_status=(
                    ExecutionStepStatus.COMPLETED
                ),
            )

            attempt_row = connection.execute(
                """
                SELECT status
                FROM task_execution_attempts
                WHERE id = ?
                """,
                (step.attempt_id,),
            ).fetchone()

            if (
                attempt_row is None
                or attempt_row["status"]
                != "running"
            ):
                raise ValueError(
                    "El intento no esta activo"
                )

            cursor = connection.execute(
                """
                UPDATE task_execution_steps
                SET
                    status = 'completed',
                    finished_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    exit_code = 0,
                    stdout_text = ?,
                    stderr_text = ?,
                    error_message = NULL
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    stdout_text or None,
                    stderr_text or None,
                    step.id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo completar "
                    "el paso"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        completed = self.get_by_id(
            step_id
        )

        if completed is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el paso completado"
            )

        return completed

    def fail(
        self,
        step_id: int,
        error_message: str,
        exit_code: int | None = None,
        stdout_text: str | None = None,
        stderr_text: str | None = None,
    ) -> ExecutionStep:
        if step_id <= 0:
            raise ValueError(
                "step_id debe ser mayor "
                "que cero"
            )

        error_message = error_message.strip()

        if not error_message:
            raise ValueError(
                "error_message no puede "
                "estar vacio"
            )

        stdout_text = (
            stdout_text.strip()
            if stdout_text is not None
            else None
        )
        stderr_text = (
            stderr_text.strip()
            if stderr_text is not None
            else None
        )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            step = self.get_by_id(
                step_id
            )

            if step is None:
                raise ValueError(
                    "No existe el paso"
                )

            self._state_machine.validate_transition(
                current_status=step.status,
                target_status=(
                    ExecutionStepStatus.FAILED
                ),
            )

            attempt_row = connection.execute(
                """
                SELECT status
                FROM task_execution_attempts
                WHERE id = ?
                """,
                (step.attempt_id,),
            ).fetchone()

            if (
                attempt_row is None
                or attempt_row["status"]
                != "running"
            ):
                raise ValueError(
                    "El intento no esta activo"
                )

            cursor = connection.execute(
                """
                UPDATE task_execution_steps
                SET
                    status = 'failed',
                    finished_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    exit_code = ?,
                    stdout_text = ?,
                    stderr_text = ?,
                    error_message = ?
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    exit_code,
                    stdout_text or None,
                    stderr_text or None,
                    error_message,
                    step.id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo registrar "
                    "el fallo del paso"
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        failed = self.get_by_id(
            step_id
        )

        if failed is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el paso fallido"
            )

        return failed

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> ExecutionStep:
        return ExecutionStep(
            id=row["id"],
            attempt_id=row["attempt_id"],
            step_number=row["step_number"],
            name=row["name"],
            action_type=row["action_type"],
            status=ExecutionStepStatus(
                row["status"]
            ),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exit_code=row["exit_code"],
            stdout_text=row["stdout_text"],
            stderr_text=row["stderr_text"],
            error_message=(
                row["error_message"]
            ),
        )