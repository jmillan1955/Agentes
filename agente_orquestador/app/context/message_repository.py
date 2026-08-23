from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from app.context.database import ContextDatabase
from app.context.models import MessageRecord
from app.models import (
    IncomingMessage,
    OutgoingMessage,
)


class MessageRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def save_incoming(
        self,
        session_id: int,
        message: IncomingMessage,
    ) -> MessageRecord:
        return self._save(
            session_id=session_id,
            message_id=message.message_id,
            correlation_id=None,
            direction="incoming",
            channel=message.channel.value,
            content_type=message.content_type.value,
            text=message.text,
            metadata=message.metadata,
            created_at=message.received_at,
        )

    def save_outgoing(
        self,
        session_id: int,
        message: OutgoingMessage,
    ) -> MessageRecord:
        return self._save(
            session_id=session_id,
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            direction="outgoing",
            channel=message.channel.value,
            content_type=message.content_type.value,
            text=message.text,
            metadata=message.metadata,
            created_at=message.created_at,
        )

    def get_by_message_id(
        self,
        channel: str,
        message_id: str,
    ) -> MessageRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                session_id,
                message_id,
                correlation_id,
                direction,
                channel,
                content_type,
                text,
                metadata_json,
                created_at
            FROM messages
            WHERE channel = ?
              AND message_id = ?
            """,
            (
                channel,
                message_id,
            ),
        ).fetchone()

        return self._to_record(row)

    def list_by_session(
        self,
        session_id: int,
    ) -> list[MessageRecord]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                session_id,
                message_id,
                correlation_id,
                direction,
                channel,
                content_type,
                text,
                metadata_json,
                created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    def list_by_project(
            self,
            project_id: int,
            limit: int = 100,
        ) -> list[MessageRecord]:
            if limit <= 0:
                raise ValueError(
                    "limit debe ser mayor que cero"
                )

            rows = self._database.connection.execute(
                """
                SELECT
                    message.id,
                    message.session_id,
                    message.message_id,
                    message.correlation_id,
                    message.direction,
                    message.channel,
                    message.content_type,
                    message.text,
                    message.metadata_json,
                    message.created_at
                FROM messages AS message
                INNER JOIN sessions AS session
                    ON session.id = message.session_id
                WHERE session.project_id = ?
                AND message.text IS NOT NULL
                AND trim(message.text) <> ''
                ORDER BY
                    message.created_at DESC,
                    message.id DESC
                LIMIT ?
                """,
                (
                    project_id,
                    limit,
                ),
            ).fetchall()

            return [
                self._to_record_required(row)
                for row in rows
            ]


    def _save(
        self,
        session_id: int,
        message_id: str,
        correlation_id: str | None,
        direction: str,
        channel: str,
        content_type: str,
        text: str | None,
        metadata: dict[str, Any],
        created_at: datetime,
    ) -> MessageRecord:
        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        connection = self._database.connection

        connection.execute(
            """
            INSERT INTO messages (
                session_id,
                message_id,
                correlation_id,
                direction,
                channel,
                content_type,
                text,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel, message_id)
            DO NOTHING
            """,
            (
                session_id,
                message_id,
                correlation_id,
                direction,
                channel,
                content_type,
                text,
                metadata_json,
                created_at.isoformat(),
            ),
        )

        connection.commit()

        saved = self.get_by_message_id(
            channel=channel,
            message_id=message_id,
        )

        if saved is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el mensaje guardado"
            )

        return saved

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> MessageRecord | None:
        if row is None:
            return None

        return MessageRepository._to_record_required(
            row
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> MessageRecord:
        return MessageRecord(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            correlation_id=row["correlation_id"],
            direction=row["direction"],
            channel=row["channel"],
            content_type=row["content_type"],
            text=row["text"],
            metadata=json.loads(
                row["metadata_json"]
            ),
            created_at=row["created_at"],
        )