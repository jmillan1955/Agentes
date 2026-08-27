from concurrent.futures import (
    ThreadPoolExecutor,
)
from pathlib import Path
import sqlite3

import pytest

from app.context import (
    ContextDatabase,
    SCHEMA_VERSION,
    initialize_schema,
)


EXPECTED_TABLES = {
    "projects",
    "sessions",
    "messages",
    "tasks",
    "task_clarification_responses",
    "task_plans",
    "task_approvals",
    "documents",
    "git_commits",
    "task_approvals",
}


EXPECTED_TASK_COLUMNS = {
    "id",
    "project_id",
    "session_id",
    "source_message_id",
    "title",
    "description",
    "target_project_name",
    "status",
    "missing_information_json",
    "plan_json",
    "created_at",
    "updated_at",
    "authorized_at",
    "completed_at",
}


def get_table_names(
    database: ContextDatabase,
) -> set[str]:
    rows = database.connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def test_creates_database_and_tables(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "context.db"
    )

    with ContextDatabase(
        database_path
    ) as database:
        tables = get_table_names(database)

        assert EXPECTED_TABLES <= tables

        version = database.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        assert version == SCHEMA_VERSION

    assert database_path.is_file()


def test_creates_task_columns() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        rows = database.connection.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()

        columns = {
            row["name"]
            for row in rows
        }

        assert (
            EXPECTED_TASK_COLUMNS
            <= columns
        )


def test_creates_task_foreign_keys() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        rows = database.connection.execute(
            "PRAGMA foreign_key_list(tasks)"
        ).fetchall()

        references = {
            (
                row["from"],
                row["table"],
                row["to"],
            )
            for row in rows
        }

        assert (
            "project_id",
            "projects",
            "id",
        ) in references

        assert (
            "session_id",
            "sessions",
            "id",
        ) in references


def test_updates_existing_database(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "existing_context.db"
    )

    connection = sqlite3.connect(
        database_path
    )

    connection.execute(
        """
        CREATE TABLE legacy_marker (
            id INTEGER PRIMARY KEY
        )
        """
    )
    connection.execute(
        "PRAGMA user_version = 2"
    )
    connection.commit()
    connection.close()

    with ContextDatabase(
        database_path
    ) as database:
        tables = get_table_names(database)

        assert "legacy_marker" in tables
        assert "tasks" in tables

        version = database.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        assert version == SCHEMA_VERSION


def test_rejects_newer_schema(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "future_context.db"
    )

    connection = sqlite3.connect(
        database_path
    )
    connection.execute(
        "PRAGMA user_version = 999"
    )
    connection.commit()
    connection.close()

    with pytest.raises(
        RuntimeError,
        match=(
            "versión de esquema "
            "más reciente"
        ),
    ):
        ContextDatabase(
            database_path
        ).connect()


def test_activates_foreign_keys_and_wal(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "context.db"
    )

    with ContextDatabase(
        database_path
    ) as database:
        foreign_keys = (
            database.connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
        )

        journal_mode = (
            database.connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
        )

        assert foreign_keys == 1
        assert journal_mode.lower() == "wal"


def test_schema_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        initialize_schema(
            database.connection
        )
        initialize_schema(
            database.connection
        )

        tables = get_table_names(database)

        assert EXPECTED_TABLES <= tables


def test_memory_database_does_not_create_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with ContextDatabase(
        ":memory:"
    ) as database:
        tables = get_table_names(database)

        assert EXPECTED_TABLES <= tables

    assert list(tmp_path.iterdir()) == []


def test_connection_is_unavailable_after_close() -> None:
    database = ContextDatabase(
        ":memory:"
    )

    database.connect()
    database.close()

    with pytest.raises(
        RuntimeError,
        match="no está conectada",
    ):
        _ = database.connection


def test_allows_connection_from_worker_thread(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "thread_context.db"
    )

    with ContextDatabase(
        database_path
    ) as database:

        def query_database() -> int:
            row = (
                database.connection
                .execute("SELECT 1")
                .fetchone()
            )

            return int(row[0])

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            result = executor.submit(
                query_database
            ).result()

        assert result == 1