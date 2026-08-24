from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType


class ContextDatabase:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = str(database_path)
        self._connection: sqlite3.Connection | None = None

    @property
    def database_path(self) -> str:
        return self._database_path

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError(
                "La base de datos no está conectada"
            )

        return self._connection

    def connect(self) -> "ContextDatabase":
        if self._connection is not None:
            return self

        if self._database_path != ":memory:":
            path = Path(self._database_path)
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False,
        )
        try:
            connection.row_factory = sqlite3.Row

            connection.execute(
                "PRAGMA foreign_keys = ON"
            )
            connection.execute(
                "PRAGMA busy_timeout = 5000"
            )

            if self._database_path != ":memory:":
                connection.execute(
                    "PRAGMA journal_mode = WAL"
                )

            from app.context.schema import (
                initialize_schema,
            )

            initialize_schema(connection)

        except Exception:
            connection.close()
            raise

        self._connection = connection
        return self

    def close(self) -> None:
        if self._connection is None:
            return

        self._connection.close()
        self._connection = None

    def __enter__(self) -> "ContextDatabase":
        return self.connect()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()