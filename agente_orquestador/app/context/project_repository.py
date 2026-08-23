from __future__ import annotations

import sqlite3

from app.context.database import ContextDatabase
from app.context.models import ProjectRecord


class ProjectRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def save(
        self,
        name: str,
        root_path: str,
        git_repository: str | None = None,
        active: bool = True,
    ) -> ProjectRecord:
        name = name.strip()
        root_path = root_path.strip()

        if not name:
            raise ValueError(
                "El nombre del proyecto "
                "no puede estar vacío"
            )

        if not root_path:
            raise ValueError(
                "La ruta del proyecto "
                "no puede estar vacía"
            )

        connection = self._database.connection

        connection.execute(
            """
            INSERT INTO projects (
                name,
                root_path,
                git_repository,
                active
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                root_path = excluded.root_path,
                git_repository = excluded.git_repository,
                active = excluded.active,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            """,
            (
                name,
                root_path,
                git_repository,
                int(active),
            ),
        )

        connection.commit()

        project = self.get_by_name(name)

        if project is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el proyecto guardado"
            )

        return project

    def get_by_id(
        self,
        project_id: int,
    ) -> ProjectRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                name,
                root_path,
                git_repository,
                active,
                created_at,
                updated_at
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        return self._to_record(row)

    def get_by_name(
        self,
        name: str,
    ) -> ProjectRecord | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                name,
                root_path,
                git_repository,
                active,
                created_at,
                updated_at
            FROM projects
            WHERE name = ?
            """,
            (name.strip(),),
        ).fetchone()

        return self._to_record(row)

    def list_active(
        self,
    ) -> list[ProjectRecord]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                name,
                root_path,
                git_repository,
                active,
                created_at,
                updated_at
            FROM projects
            WHERE active = 1
            ORDER BY name
            """
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> ProjectRecord | None:
        if row is None:
            return None

        return ProjectRepository._to_record_required(
            row
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> ProjectRecord:
        return ProjectRecord(
            id=row["id"],
            name=row["name"],
            root_path=row["root_path"],
            git_repository=row["git_repository"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )