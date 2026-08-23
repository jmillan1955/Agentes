from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.context.models import DocumentRecord


class DocumentRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def save(
        self,
        project_id: int,
        relative_path: str,
        content: str,
        content_hash: str,
        title: str | None = None,
        file_modified_at: str | None = None,
        git_commit_hash: str | None = None,
    ) -> DocumentRecord:
        relative_path = relative_path.strip()
        content_hash = content_hash.strip()

        if not relative_path:
            raise ValueError(
                "relative_path no puede estar vacío"
            )

        if not content_hash:
            raise ValueError(
                "content_hash no puede estar vacío"
            )

        existing = self.get_by_path(
            project_id=project_id,
            relative_path=relative_path,
        )

        if (
            existing is not None
            and existing.content_hash
            == content_hash
        ):
            return existing

        connection = self._database.connection

        connection.execute(
            """
            INSERT INTO documents (
                project_id,
                relative_path,
                title,
                content,
                content_hash,
                file_modified_at,
                git_commit_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                project_id,
                relative_path
            )
            DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                content_hash = excluded.content_hash,
                file_modified_at = (
                    excluded.file_modified_at
                ),
                synchronized_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                ),
                git_commit_hash = (
                    excluded.git_commit_hash
                )
            """,
            (
                project_id,
                relative_path,
                title,
                content,
                content_hash,
                file_modified_at,
                git_commit_hash,
            ),
        )

        connection.commit()

        saved = self.get_by_path(
            project_id=project_id,
            relative_path=relative_path,
        )

        if saved is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el documento guardado"
            )

        return saved

    def get_by_path(
        self,
        project_id: int,
        relative_path: str,
    ) -> DocumentRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                relative_path,
                title,
                content,
                content_hash,
                file_modified_at,
                synchronized_at,
                git_commit_hash
            FROM documents
            WHERE project_id = ?
              AND relative_path = ?
            """,
            (
                project_id,
                relative_path.strip(),
            ),
        ).fetchone()

        return self._to_record(row)

    def list_by_project(
        self,
        project_id: int,
    ) -> list[DocumentRecord]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                project_id,
                relative_path,
                title,
                content,
                content_hash,
                file_modified_at,
                synchronized_at,
                git_commit_hash
            FROM documents
            WHERE project_id = ?
            ORDER BY relative_path
            """,
            (project_id,),
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> DocumentRecord | None:
        if row is None:
            return None

        return DocumentRepository._to_record_required(
            row
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            project_id=row["project_id"],
            relative_path=row["relative_path"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            file_modified_at=(
                row["file_modified_at"]
            ),
            synchronized_at=(
                row["synchronized_at"]
            ),
            git_commit_hash=(
                row["git_commit_hash"]
            ),
        )