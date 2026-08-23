from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.context.models import SessionRecord


class SessionRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_or_create_active(
        self,
        project_id: int,
        channel: str,
        user_id: str,
        conversation_id: str,
    ) -> SessionRecord:
        channel = channel.strip()
        user_id = user_id.strip()
        conversation_id = conversation_id.strip()

        if not channel:
            raise ValueError(
                "channel no puede estar vacío"
            )

        if not user_id:
            raise ValueError(
                "user_id no puede estar vacío"
            )

        if not conversation_id:
            raise ValueError(
                "conversation_id no puede estar vacío"
            )

        existing = self.get_active(
            project_id=project_id,
            channel=channel,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        if existing is not None:
            return existing

        connection = self._database.connection

        connection.execute(
            """
            INSERT INTO sessions (
                project_id,
                channel,
                user_id,
                conversation_id,
                status
            )
            VALUES (?, ?, ?, ?, 'active')
            """,
            (
                project_id,
                channel,
                user_id,
                conversation_id,
            ),
        )

        connection.commit()

        created = self.get_active(
            project_id=project_id,
            channel=channel,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la sesión creada"
            )

        return created

    def get_active(
        self,
        project_id: int,
        channel: str,
        user_id: str,
        conversation_id: str,
    ) -> SessionRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                channel,
                user_id,
                conversation_id,
                status,
                started_at,
                ended_at
            FROM sessions
            WHERE project_id = ?
              AND channel = ?
              AND user_id = ?
              AND conversation_id = ?
              AND status = 'active'
            """,
            (
                project_id,
                channel,
                user_id,
                conversation_id,
            ),
        ).fetchone()

        return self._to_record(row)

    def get_by_id(
        self,
        session_id: int,
    ) -> SessionRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                channel,
                user_id,
                conversation_id,
                status,
                started_at,
                ended_at
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        return self._to_record(row)

    def close(
        self,
        session_id: int,
    ) -> SessionRecord | None:
        connection = self._database.connection

        connection.execute(
            """
            UPDATE sessions
            SET
                status = 'closed',
                ended_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            WHERE id = ?
              AND status = 'active'
            """,
            (session_id,),
        )

        connection.commit()

        return self.get_by_id(session_id)

    def list_active(
        self,
    ) -> list[SessionRecord]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                channel,
                user_id,
                conversation_id,
                status,
                started_at,
                ended_at
            FROM sessions
            WHERE status = 'active'
            ORDER BY started_at
            """
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> SessionRecord | None:
        if row is None:
            return None

        return SessionRepository._to_record_required(
            row
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            project_id=row["project_id"],
            channel=row["channel"],
            user_id=row["user_id"],
            conversation_id=row["conversation_id"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
        )