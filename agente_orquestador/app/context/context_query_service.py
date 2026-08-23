from __future__ import annotations

from app.context.database import ContextDatabase
from app.context.models import (
    ContextCommitSummary,
    ContextDocumentSummary,
    ContextSummary,
)


class ContextQueryService:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_summary(
        self,
        project_id: int,
        recent_limit: int = 5,
    ) -> ContextSummary:
        if recent_limit <= 0:
            raise ValueError(
                "recent_limit debe ser "
                "mayor que cero"
            )

        connection = self._database.connection

        project = connection.execute(
            """
            SELECT id, name
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError(
                f"No existe el proyecto {project_id}"
            )

        total_sessions = self._count(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE project_id = ?
            """,
            project_id,
        )

        active_sessions = self._count(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE project_id = ?
              AND status = 'active'
            """,
            project_id,
        )

        total_messages = self._count(
            """
            SELECT COUNT(*)
            FROM messages AS message
            INNER JOIN sessions AS session
                ON session.id = message.session_id
            WHERE session.project_id = ?
            """,
            project_id,
        )

        total_documents = self._count(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE project_id = ?
            """,
            project_id,
        )

        total_commits = self._count(
            """
            SELECT COUNT(*)
            FROM git_commits
            WHERE project_id = ?
            """,
            project_id,
        )

        document_rows = connection.execute(
            """
            SELECT
                relative_path,
                title,
                synchronized_at
            FROM documents
            WHERE project_id = ?
            ORDER BY
                synchronized_at DESC,
                id DESC
            LIMIT ?
            """,
            (
                project_id,
                recent_limit,
            ),
        ).fetchall()

        commit_rows = connection.execute(
            """
            SELECT
                commit_hash,
                subject,
                authored_at
            FROM git_commits
            WHERE project_id = ?
            ORDER BY
                authored_at DESC,
                commit_hash
            LIMIT ?
            """,
            (
                project_id,
                recent_limit,
            ),
        ).fetchall()

        recent_documents = tuple(
            ContextDocumentSummary(
                relative_path=(
                    row["relative_path"]
                ),
                title=row["title"],
                synchronized_at=(
                    row["synchronized_at"]
                ),
            )
            for row in document_rows
        )

        recent_commits = tuple(
            ContextCommitSummary(
                commit_hash=row["commit_hash"],
                subject=row["subject"],
                authored_at=row["authored_at"],
            )
            for row in commit_rows
        )

        return ContextSummary(
            project_id=project["id"],
            project_name=project["name"],
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_messages=total_messages,
            total_documents=total_documents,
            total_commits=total_commits,
            recent_documents=recent_documents,
            recent_commits=recent_commits,
        )

    def _count(
        self,
        sql: str,
        project_id: int,
    ) -> int:
        row = self._database.connection.execute(
            sql,
            (project_id,),
        ).fetchone()

        return int(row[0])