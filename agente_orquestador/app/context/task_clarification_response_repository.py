from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from app.context.database import ContextDatabase
from app.tasks import (
    TaskClarificationResponse,
    TaskStatus,
)


class TaskClarificationResponseRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def create(
        self,
        task_id: int,
        response_message_id: str,
        questions: Iterable[str],
        answer: str,
    ) -> TaskClarificationResponse:
        if task_id <= 0:
            raise ValueError(
                "task_id debe ser mayor que cero"
            )

        response_message_id = (
            response_message_id.strip()
        )

        answer = answer.strip()

        question_values = tuple(
            question.strip()
            for question in questions
            if question.strip()
        )

        if not response_message_id:
            raise ValueError(
                "response_message_id no puede "
                "estar vacío"
            )

        if not question_values:
            raise ValueError(
                "questions no puede estar vacío"
            )

        if not answer:
            raise ValueError(
                "answer no puede estar vacío"
            )

        existing = self.get_by_response_message(
            task_id=task_id,
            response_message_id=(
                response_message_id
            ),
        )

        if existing is not None:
            return existing

        self._validate_task(task_id)

        cursor = (
            self._database.connection.execute(
                """
                INSERT INTO
                    task_clarification_responses (
                        task_id,
                        response_message_id,
                        questions_json,
                        answer
                    )
                VALUES (?, ?, ?, ?)
                """,
                (
                    task_id,
                    response_message_id,
                    json.dumps(
                        question_values,
                        ensure_ascii=False,
                    ),
                    answer,
                ),
            )
        )

        self._database.connection.commit()

        created = self.get_by_id(
            int(cursor.lastrowid)
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar la "
                "respuesta de aclaración creada"
            )

        return created

    def get_by_id(
        self,
        response_id: int,
    ) -> TaskClarificationResponse | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                response_message_id,
                questions_json,
                answer,
                created_at
            FROM task_clarification_responses
            WHERE id = ?
            """,
            (response_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_response_message(
        self,
        task_id: int,
        response_message_id: str,
    ) -> TaskClarificationResponse | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                response_message_id,
                questions_json,
                answer,
                created_at
            FROM task_clarification_responses
            WHERE task_id = ?
              AND response_message_id = ?
            """,
            (
                task_id,
                response_message_id.strip(),
            ),
        ).fetchone()

        return self._to_record(row)

    def list_by_task(
        self,
        task_id: int,
    ) -> list[TaskClarificationResponse]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                response_message_id,
                questions_json,
                answer,
                created_at
            FROM task_clarification_responses
            WHERE task_id = ?
            ORDER BY created_at, id
            """,
            (task_id,),
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    def _validate_task(
        self,
        task_id: int,
    ) -> None:
        row = self._database.connection.execute(
            """
            SELECT status
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"No existe la tarea #{task_id}"
            )

        status = TaskStatus(row["status"])

        if (
            status
            != TaskStatus.PENDING_CLARIFICATION
        ):
            raise ValueError(
                "La tarea no está pendiente "
                "de aclaración"
            )

    @staticmethod
    def _decode_questions(
        value: str,
    ) -> tuple[str, ...]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "questions_json contiene "
                "un JSON no válido"
            ) from error

        if not isinstance(decoded, list):
            raise RuntimeError(
                "questions_json debe contener "
                "una lista JSON"
            )

        if not all(
            isinstance(item, str)
            for item in decoded
        ):
            raise RuntimeError(
                "questions_json debe contener "
                "solamente textos"
            )

        return tuple(decoded)

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskClarificationResponse | None:
        if row is None:
            return None

        return (
            TaskClarificationResponseRepository
            ._to_record_required(row)
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> TaskClarificationResponse:
        return TaskClarificationResponse(
            id=row["id"],
            task_id=row["task_id"],
            response_message_id=(
                row["response_message_id"]
            ),
            questions=(
                TaskClarificationResponseRepository
                ._decode_questions(
                    row["questions_json"]
                )
            ),
            answer=row["answer"],
            created_at=row["created_at"],
        )