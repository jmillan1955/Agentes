from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.execution.models import (
    ExecutionAttempt,
    ExecutionAttemptStatus,
)


class TaskExecutionAttemptRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_by_id(
        self,
        attempt_id: int,
    ) -> ExecutionAttempt | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                attempt_number,
                status,
                started_at,
                finished_at,
                exit_code,
                error_message
            FROM task_execution_attempts
            WHERE id = ?
            """,
            (attempt_id,),
        ).fetchone()

        return self._to_record(row)

    def get_current(
        self,
        execution_id: int,
    ) -> ExecutionAttempt | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                attempt_number,
                status,
                started_at,
                finished_at,
                exit_code,
                error_message
            FROM task_execution_attempts
            WHERE execution_id = ?
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            (execution_id,),
        ).fetchone()

        return self._to_record(row)

    def list_by_execution(
        self,
        execution_id: int,
    ) -> tuple[ExecutionAttempt, ...]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                attempt_number,
                status,
                started_at,
                finished_at,
                exit_code,
                error_message
            FROM task_execution_attempts
            WHERE execution_id = ?
            ORDER BY attempt_number
            """,
            (execution_id,),
        ).fetchall()

        return tuple(
            self._to_record_required(row)
            for row in rows
        )

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> ExecutionAttempt | None:
        if row is None:
            return None

        return (
            TaskExecutionAttemptRepository
            ._to_record_required(row)
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> ExecutionAttempt:
        return ExecutionAttempt(
            id=row["id"],
            execution_id=row["execution_id"],
            attempt_number=(
                row["attempt_number"]
            ),
            status=ExecutionAttemptStatus(
                row["status"]
            ),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exit_code=row["exit_code"],
            error_message=(
                row["error_message"]
            ),
        )