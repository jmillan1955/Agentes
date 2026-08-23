from pathlib import Path

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
    "documents",
    "git_commits",
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