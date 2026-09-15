from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    telegram_chat_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT 'Nueva conversación',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_conversation_per_chat
ON conversations(user_id, telegram_chat_id)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    telegram_chat_id INTEGER NOT NULL,
    telegram_message_id INTEGER,
    direction TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    content_type TEXT NOT NULL,
    text TEXT,
    model TEXT,
    reasoning_effort TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    UNIQUE (telegram_chat_id, telegram_message_id, direction)
);

CREATE INDEX IF NOT EXISTS messages_by_conversation
ON messages(conversation_id, id);
"""


@dataclass(frozen=True, slots=True)
class Conversation:
    id: int
    user_id: int
    telegram_chat_id: int
    title: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: int
    conversation_id: int
    direction: str
    content_type: str
    text: str | None
    model: str | None
    created_at: str


class ConversationStore:
    """Historial SQLite aislado por usuario y conversación de Telegram."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self._lock = RLock()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_or_create_user(
        self,
        telegram_user_id: int,
        *,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> int:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (telegram_user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (telegram_user_id, username, first_name, last_name),
            )
            row = connection.execute(
                "SELECT id FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,),
            ).fetchone()
            return int(row["id"])

    def get_or_create_active_conversation(
        self, user_id: int, telegram_chat_id: int
    ) -> Conversation:
        with self._lock, self._connect() as connection:
            row = self._active_row(connection, user_id, telegram_chat_id)
            if row is None:
                cursor = connection.execute(
                    """
                    INSERT INTO conversations (user_id, telegram_chat_id)
                    VALUES (?, ?)
                    """,
                    (user_id, telegram_chat_id),
                )
                row = connection.execute(
                    "SELECT * FROM conversations WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            return self._conversation(row)

    def get_active_conversation(
        self, user_id: int, telegram_chat_id: int
    ) -> Conversation | None:
        with self._lock, self._connect() as connection:
            row = self._active_row(connection, user_id, telegram_chat_id)
            return self._conversation(row) if row is not None else None

    def start_new_conversation(
        self,
        user_id: int,
        telegram_chat_id: int,
        *,
        title: str = "Nueva conversación",
    ) -> Conversation:
        clean_title = " ".join(title.split()).strip()
        if not clean_title:
            raise ValueError("El nombre de la conversación no puede estar vacío.")
        if len(clean_title) > 70:
            raise ValueError("El nombre de la conversación no puede superar 70 caracteres.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET status = 'archived',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE user_id = ? AND telegram_chat_id = ? AND status = 'active'
                """,
                (user_id, telegram_chat_id),
            )
            cursor = connection.execute(
                """
                INSERT INTO conversations (user_id, telegram_chat_id, title)
                VALUES (?, ?, ?)
                """,
                (user_id, telegram_chat_id, clean_title),
            )
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._conversation(row)

    def activate_conversation(
        self, user_id: int, telegram_chat_id: int, conversation_id: int
    ) -> Conversation | None:
        with self._lock, self._connect() as connection:
            selected = connection.execute(
                """
                SELECT * FROM conversations
                WHERE id = ? AND user_id = ? AND telegram_chat_id = ?
                """,
                (conversation_id, user_id, telegram_chat_id),
            ).fetchone()
            if selected is None:
                return None
            connection.execute(
                """
                UPDATE conversations SET status = 'archived'
                WHERE user_id = ? AND telegram_chat_id = ? AND status = 'active'
                """,
                (user_id, telegram_chat_id),
            )
            connection.execute(
                """
                UPDATE conversations
                SET status = 'active',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (conversation_id,),
            )
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            return self._conversation(row)

    def list_conversations(self, user_id: int, limit: int = 10) -> list[Conversation]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [self._conversation(row) for row in rows]

    def save_message(
        self,
        conversation_id: int,
        telegram_chat_id: int,
        *,
        telegram_message_id: int | None,
        direction: str,
        content_type: str,
        text: str | None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO messages (
                    conversation_id, telegram_chat_id, telegram_message_id,
                    direction, content_type, text, model, reasoning_effort,
                    input_tokens, output_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    telegram_chat_id,
                    telegram_message_id,
                    direction,
                    content_type,
                    text,
                    model,
                    reasoning_effort,
                    input_tokens,
                    output_tokens,
                ),
            )
            if cursor.rowcount:
                connection.execute(
                    """
                    UPDATE conversations
                    SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                        title = CASE
                            WHEN title = 'Nueva conversación'
                             AND ? = 'incoming'
                             AND trim(coalesce(?, '')) <> ''
                            THEN substr(trim(?), 1, 70)
                            ELSE title
                        END
                    WHERE id = ?
                    """,
                    (direction, text, text, conversation_id),
                )
            return bool(cursor.rowcount)

    def recent_messages(
        self, conversation_id: int, limit: int = 20
    ) -> list[StoredMessage]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, direction, content_type, text, model, created_at
                FROM messages
                WHERE conversation_id = ? AND text IS NOT NULL AND trim(text) <> ''
                ORDER BY id DESC LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
            return [self._message(row) for row in reversed(rows)]

    def context_text(
        self, conversation_id: int, *, limit: int = 20, max_characters: int = 12000
    ) -> str:
        messages = self.recent_messages(conversation_id, limit)
        lines = [
            f"{'Usuario' if message.direction == 'incoming' else 'Asistente'}: {message.text}"
            for message in messages
        ]
        selected: list[str] = []
        size = 0
        for line in reversed(lines):
            if selected and size + len(line) + 1 > max_characters:
                break
            selected.append(line)
            size += len(line) + 1
        return "\n".join(reversed(selected))

    @staticmethod
    def _active_row(
        connection: sqlite3.Connection, user_id: int, telegram_chat_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM conversations
            WHERE user_id = ? AND telegram_chat_id = ? AND status = 'active'
            """,
            (user_id, telegram_chat_id),
        ).fetchone()

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(**dict(row))

    @staticmethod
    def _message(row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(**dict(row))
