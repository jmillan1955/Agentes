from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.context.models import GitCommitRecord


class GitCommitRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def save(
        self,
        commit_hash: str,
        project_id: int,
        authored_at: str,
        subject: str,
        parent_hash: str | None = None,
        author_name: str | None = None,
        body: str | None = None,
    ) -> GitCommitRecord:
        commit_hash = commit_hash.strip()
        authored_at = authored_at.strip()
        subject = subject.strip()

        if not commit_hash:
            raise ValueError(
                "commit_hash no puede estar vacío"
            )

        if not authored_at:
            raise ValueError(
                "authored_at no puede estar vacío"
            )

        if not subject:
            raise ValueError(
                "subject no puede estar vacío"
            )

        connection = self._database.connection

        connection.execute(
            """
            INSERT INTO git_commits (
                commit_hash,
                project_id,
                parent_hash,
                author_name,
                authored_at,
                subject,
                body
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(commit_hash)
            DO UPDATE SET
                project_id = excluded.project_id,
                parent_hash = excluded.parent_hash,
                author_name = excluded.author_name,
                authored_at = excluded.authored_at,
                subject = excluded.subject,
                body = excluded.body,
                synchronized_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            """,
            (
                commit_hash,
                project_id,
                parent_hash,
                author_name,
                authored_at,
                subject,
                body,
            ),
        )

        connection.commit()

        saved = self.get_by_hash(
            commit_hash
        )

        if saved is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el commit guardado"
            )

        return saved

    def get_by_hash(
        self,
        commit_hash: str,
    ) -> GitCommitRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                commit_hash,
                project_id,
                parent_hash,
                author_name,
                authored_at,
                subject,
                body,
                synchronized_at
            FROM git_commits
            WHERE commit_hash = ?
            """,
            (commit_hash.strip(),),
        ).fetchone()

        return self._to_record(row)

    def list_by_project(
        self,
        project_id: int,
    ) -> list[GitCommitRecord]:
        rows = self._database.connection.execute(
            """
            SELECT
                commit_hash,
                project_id,
                parent_hash,
                author_name,
                authored_at,
                subject,
                body,
                synchronized_at
            FROM git_commits
            WHERE project_id = ?
            ORDER BY authored_at DESC, commit_hash
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
    ) -> GitCommitRecord | None:
        if row is None:
            return None

        return (
            GitCommitRepository
            ._to_record_required(row)
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> GitCommitRecord:
        return GitCommitRecord(
            commit_hash=row["commit_hash"],
            project_id=row["project_id"],
            parent_hash=row["parent_hash"],
            author_name=row["author_name"],
            authored_at=row["authored_at"],
            subject=row["subject"],
            body=row["body"],
            synchronized_at=(
                row["synchronized_at"]
            ),
        )