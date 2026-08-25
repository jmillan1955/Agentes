from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from app.context.database import ContextDatabase
from app.tasks import (
    TaskRecord,
    TaskStateMachine,
    TaskStatus,
)


class TaskRepository:
    def __init__(
        self,
        database: ContextDatabase,
        state_machine: (
            TaskStateMachine | None
        ) = None,
    ) -> None:
        self._database = database
        self._state_machine = (
            state_machine
            or TaskStateMachine()
        )
    def create(
        self,
        project_id: int,
        session_id: int,
        source_message_id: str,
        title: str,
        description: str,
        target_project_name: str | None = None,
        status: TaskStatus = (
            TaskStatus.PENDING_PLANNING
        ),
        missing_information: Iterable[
            str
        ] = (),
        plan: Iterable[str] = (),
    ) -> TaskRecord:
        if project_id <= 0:
            raise ValueError(
                "project_id debe ser "
                "mayor que cero"
            )

        if session_id <= 0:
            raise ValueError(
                "session_id debe ser "
                "mayor que cero"
            )

        source_message_id = (
            source_message_id.strip()
        )
        title = title.strip()
        description = description.strip()

        if not source_message_id:
            raise ValueError(
                "source_message_id no puede "
                "estar vacío"
            )

        if not title:
            raise ValueError(
                "title no puede estar vacío"
            )

        if not description:
            raise ValueError(
                "description no puede "
                "estar vacía"
            )

        target_project_name = (
            target_project_name.strip()
            if target_project_name is not None
            else None
        )

        target_project_name = (
            target_project_name or None
        )

        missing_information_tuple = tuple(
            value.strip()
            for value in missing_information
            if value.strip()
        )

        plan_tuple = tuple(
            step.strip()
            for step in plan
            if step.strip()
        )

        self._validate_session_project(
            project_id=project_id,
            session_id=session_id,
        )

        existing = self.get_by_source_message(
            session_id=session_id,
            source_message_id=(
                source_message_id
            ),
        )

        if existing is not None:
            return existing

        cursor = (
            self._database.connection.execute(
                """
                INSERT INTO tasks (
                    project_id,
                    session_id,
                    source_message_id,
                    title,
                    description,
                    target_project_name,
                    status,
                    missing_information_json,
                    plan_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    session_id,
                    source_message_id,
                    title,
                    description,
                    target_project_name,
                    status.value,
                    json.dumps(
                        missing_information_tuple,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        plan_tuple,
                        ensure_ascii=False,
                    ),
                ),
            )
        )

        self._database.connection.commit()

        created = self.get_by_id(
            int(cursor.lastrowid)
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la tarea creada"
            )

        return created

    def get_by_id(
        self,
        task_id: int,
    ) -> TaskRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                session_id,
                source_message_id,
                title,
                description,
                target_project_name,
                status,
                missing_information_json,
                plan_json,
                created_at,
                updated_at,
                authorized_at,
                completed_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_source_message(
        self,
        session_id: int,
        source_message_id: str,
    ) -> TaskRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                session_id,
                source_message_id,
                title,
                description,
                target_project_name,
                status,
                missing_information_json,
                plan_json,
                created_at,
                updated_at,
                authorized_at,
                completed_at
            FROM tasks
            WHERE session_id = ?
              AND source_message_id = ?
            """,
            (
                session_id,
                source_message_id,
            ),
        ).fetchone()

        return self._to_record(row)

    def list_by_project(
        self,
        project_id: int,
        status: TaskStatus | None = None,
    ) -> list[TaskRecord]:
        if status is None:
            rows = (
                self._database.connection
                .execute(
                    """
                    SELECT
                        id,
                        project_id,
                        session_id,
                        source_message_id,
                        title,
                        description,
                        target_project_name,
                        status,
                        missing_information_json,
                        plan_json,
                        created_at,
                        updated_at,
                        authorized_at,
                        completed_at
                    FROM tasks
                    WHERE project_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (project_id,),
                )
                .fetchall()
            )

        else:
            rows = (
                self._database.connection
                .execute(
                    """
                    SELECT
                        id,
                        project_id,
                        session_id,
                        source_message_id,
                        title,
                        description,
                        target_project_name,
                        status,
                        missing_information_json,
                        plan_json,
                        created_at,
                        updated_at,
                        authorized_at,
                        completed_at
                    FROM tasks
                    WHERE project_id = ?
                      AND status = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (
                        project_id,
                        status.value,
                    ),
                )
                .fetchall()
            )

        return [
            self._to_record_required(row)
            for row in rows
        ]

    def set_missing_information(
        self,
        task_id: int,
        missing_information: Iterable[str],
    ) -> TaskRecord:
        values = tuple(
            value.strip()
            for value in missing_information
            if value.strip()
        )

        if not values:
            raise ValueError(
                "missing_information no puede "
                "estar vacío"
            )

        task = self._get_required(task_id)

        self._state_machine.validate_transition(
            current_status=task.status,
            target_status=(
                TaskStatus.PENDING_CLARIFICATION
            ),
        )

        self._database.connection.execute(
            """
            UPDATE tasks
            SET
                status = ?,
                missing_information_json = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            WHERE id = ?
            """,
            (
                (
                    TaskStatus
                    .PENDING_CLARIFICATION
                    .value
                ),
                json.dumps(
                    values,
                    ensure_ascii=False,
                ),
                task_id,
            ),
        )

        self._database.connection.commit()

        return self._get_required(task_id)

    def return_to_planning(
        self,
        task_id: int,
    ) -> TaskRecord:
        task = self._get_required(task_id)

        self._state_machine.validate_transition(
            current_status=task.status,
            target_status=(
                TaskStatus.PENDING_PLANNING
            ),
        )

        self._database.connection.execute(
            """
            UPDATE tasks
            SET
                status = ?,
                missing_information_json = '[]',
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            WHERE id = ?
            """,
            (
                (
                    TaskStatus
                    .PENDING_PLANNING
                    .value
                ),
                task_id,
            ),
        )

        self._database.connection.commit()

        return self._get_required(task_id)
    
    def set_plan(
        self,
        task_id: int,
        plan: Iterable[str],
    ) -> TaskRecord:
        steps = tuple(
            step.strip()
            for step in plan
            if step.strip()
        )

        if not steps:
            raise ValueError(
                "plan no puede estar vacío"
            )

        task = self._get_required(task_id)

        self._state_machine.validate_transition(
            current_status=task.status,
            target_status=(
                TaskStatus.PENDING_APPROVAL
            ),
        )

        self._database.connection.execute(
            """
            UPDATE tasks
            SET
                status = ?,
                missing_information_json = '[]',
                plan_json = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            WHERE id = ?
            """,
            (
                (
                    TaskStatus
                    .PENDING_APPROVAL
                    .value
                ),
                json.dumps(
                    steps,
                    ensure_ascii=False,
                ),
                task_id,
            ),
        )

        self._database.connection.commit()

        return self._get_required(task_id)

    def transition(
        self,
        task_id: int,
        target_status: TaskStatus,
    ) -> TaskRecord:
        task = self._get_required(task_id)

        self._state_machine.validate_transition(
            current_status=task.status,
            target_status=target_status,
        )

        self._database.connection.execute(
            """
            UPDATE tasks
            SET
                status = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                ),
                authorized_at = CASE
                    WHEN ? = 'approved'
                    THEN strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                    ELSE authorized_at
                END,
                completed_at = CASE
                    WHEN ? IN (
                        'completed',
                        'failed',
                        'cancelled'
                    )
                    THEN strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                    ELSE completed_at
                END
            WHERE id = ?
            """,
            (
                target_status.value,
                target_status.value,
                target_status.value,
                task_id,
            ),
        )

        self._database.connection.commit()

        return self._get_required(task_id)

    def approve(
        self,
        task_id: int,
    ) -> TaskRecord:
        return self.transition(
            task_id=task_id,
            target_status=TaskStatus.APPROVED,
        )

    def cancel(
        self,
        task_id: int,
    ) -> TaskRecord:
        return self.transition(
            task_id=task_id,
            target_status=TaskStatus.CANCELLED,
        )

    def _get_required(
        self,
        task_id: int,
    ) -> TaskRecord:
        task = self.get_by_id(task_id)

        if task is None:
            raise ValueError(
                f"No existe la tarea #{task_id}"
            )

        return task

    def _validate_session_project(
        self,
        project_id: int,
        session_id: int,
    ) -> None:
        row = self._database.connection.execute(
            """
            SELECT project_id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                "No existe la sesión indicada"
            )

        if row["project_id"] != project_id:
            raise ValueError(
                "La sesión no pertenece "
                "al proyecto"
            )

    @staticmethod
    def _decode_string_tuple(
        value: str,
        field_name: str,
    ) -> tuple[str, ...]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"{field_name} contiene "
                "un JSON no válido"
            ) from error

        if not isinstance(decoded, list):
            raise RuntimeError(
                f"{field_name} debe contener "
                "una lista JSON"
            )

        if not all(
            isinstance(item, str)
            for item in decoded
        ):
            raise RuntimeError(
                f"{field_name} debe contener "
                "solamente textos"
            )

        return tuple(decoded)

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskRecord | None:
        if row is None:
            return None

        return TaskRepository._to_record_required(
            row
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> TaskRecord:
        try:
            status = TaskStatus(
                row["status"]
            )
        except ValueError as error:
            raise RuntimeError(
                "La tarea contiene un "
                "estado desconocido"
            ) from error

        return TaskRecord(
            id=row["id"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            source_message_id=(
                row["source_message_id"]
            ),
            title=row["title"],
            description=row["description"],
            target_project_name=(
                row["target_project_name"]
            ),
            status=status,
            missing_information=(
                TaskRepository
                ._decode_string_tuple(
                    row[
                        "missing_information_json"
                    ],
                    "missing_information_json",
                )
            ),
            plan=(
                TaskRepository
                ._decode_string_tuple(
                    row["plan_json"],
                    "plan_json",
                )
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            authorized_at=(
                row["authorized_at"]
            ),
            completed_at=row["completed_at"],
        )