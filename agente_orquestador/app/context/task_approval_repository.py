from __future__ import annotations

import sqlite3

from app.approvals.models import (
    TaskApproval,
)
from app.context.database import ContextDatabase


class TaskApprovalRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_by_id(
        self,
        approval_id: int,
    ) -> TaskApproval | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                plan_id,
                plan_version,
                authorized_user_id,
                authorization_message_id,
                channel,
                created_at
            FROM task_approvals
            WHERE id = ?
            """,
            (approval_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_task_id(
        self,
        task_id: int,
    ) -> TaskApproval | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                plan_id,
                plan_version,
                authorized_user_id,
                authorization_message_id,
                channel,
                created_at
            FROM task_approvals
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        return self._to_record(row)

    def approve(
        self,
        task_id: int,
        plan_id: int,
        plan_version: int,
        authorized_user_id: str,
        authorization_message_id: str,
        channel: str,
    ) -> TaskApproval:
        if task_id <= 0:
            raise ValueError(
                "task_id debe ser mayor que cero"
            )

        if plan_id <= 0:
            raise ValueError(
                "plan_id debe ser mayor que cero"
            )

        if plan_version <= 0:
            raise ValueError(
                "plan_version debe ser "
                "mayor que cero"
            )

        authorized_user_id = (
            authorized_user_id.strip()
        )
        authorization_message_id = (
            authorization_message_id.strip()
        )
        channel = channel.strip()

        if not authorized_user_id:
            raise ValueError(
                "authorized_user_id no puede "
                "estar vacio"
            )

        if not authorization_message_id:
            raise ValueError(
                "authorization_message_id no puede "
                "estar vacio"
            )

        if not channel:
            raise ValueError(
                "channel no puede estar vacio"
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
                    and existing.plan_version
                    == plan_version
                ):
                    connection.rollback()
                    return existing

                raise ValueError(
                    "La tarea ya tiene aprobado "
                    "otro plan"
                )

            row = connection.execute(
                """
                SELECT
                    tasks.status AS task_status,
                    task_plans.task_id
                        AS plan_task_id,
                    task_plans.version
                        AS stored_plan_version,
                    task_plans.status
                        AS plan_status,
                    (
                        SELECT MAX(version)
                        FROM task_plans
                        WHERE task_id = tasks.id
                    ) AS latest_plan_version
                FROM tasks
                JOIN task_plans
                  ON task_plans.id = ?
                WHERE tasks.id = ?
                """,
                (
                    plan_id,
                    task_id,
                ),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "No existe la tarea o el plan"
                )

            if row["plan_task_id"] != task_id:
                raise ValueError(
                    "El plan no pertenece "
                    "a la tarea"
                )

            if (
                row["stored_plan_version"]
                != plan_version
            ):
                raise ValueError(
                    "La version del plan "
                    "no coincide"
                )

            if (
                row["latest_plan_version"]
                != plan_version
            ):
                raise ValueError(
                    "Solo se puede aprobar "
                    "la ultima version del plan"
                )

            if (
                row["task_status"]
                != "pending_approval"
            ):
                raise ValueError(
                    "La tarea no esta pendiente "
                    "de aprobacion"
                )

            if (
                row["plan_status"]
                != "pending_approval"
            ):
                raise ValueError(
                    "El plan no esta pendiente "
                    "de aprobacion"
                )

            plan_cursor = connection.execute(
                """
                UPDATE task_plans
                SET
                    status = 'approved',
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND task_id = ?
                  AND version = ?
                  AND status = 'pending_approval'
                """,
                (
                    plan_id,
                    task_id,
                    plan_version,
                ),
            )

            if plan_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo aprobar el plan"
                )

            task_cursor = connection.execute(
                """
                UPDATE tasks
                SET
                    status = 'approved',
                    authorized_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    updated_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                WHERE id = ?
                  AND status = 'pending_approval'
                """,
                (task_id,),
            )

            if task_cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo aprobar la tarea"
                )

            cursor = connection.execute(
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
                    plan_version,
                    authorized_user_id,
                    authorization_message_id,
                    channel,
                ),
            )

            approval_id = int(
                cursor.lastrowid
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        created = self.get_by_id(
            approval_id
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la autorizacion creada"
            )

        return created

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskApproval | None:
        if row is None:
            return None

        return TaskApproval(
            id=row["id"],
            task_id=row["task_id"],
            plan_id=row["plan_id"],
            plan_version=row["plan_version"],
            authorized_user_id=(
                row["authorized_user_id"]
            ),
            authorization_message_id=(
                row["authorization_message_id"]
            ),
            channel=row["channel"],
            created_at=row["created_at"],
        )