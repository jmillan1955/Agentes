import sqlite3

from app.context.schema import (
    SCHEMA_SQL,
    SCHEMA_VERSION,
    initialize_schema,
)


_TARGET_COLUMN_SQL = """
    target_subdirectory TEXT NOT NULL
        DEFAULT '.',
"""


def test_migrates_version_nine_database(
) -> None:
    connection = sqlite3.connect(
        ":memory:"
    )

    try:
        legacy_schema_sql = (
            SCHEMA_SQL.replace(
                _TARGET_COLUMN_SQL,
                "",
            )
        )

        assert (
            "target_subdirectory"
            not in legacy_schema_sql
        )

        connection.executescript(
            legacy_schema_sql
        )
        connection.execute(
            "PRAGMA user_version = 9"
        )
        connection.commit()

        initialize_schema(connection)

        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    task_execution_promotions
                )
                """
            ).fetchall()
        }

        assert (
            "target_subdirectory"
            in columns
        )

        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        assert version == SCHEMA_VERSION
        assert version == 10

    finally:
        connection.close()


def test_initializes_new_database_with_column(
) -> None:
    connection = sqlite3.connect(
        ":memory:"
    )

    try:
        initialize_schema(connection)

        column_rows = (
            connection.execute(
                """
                PRAGMA table_info(
                    task_execution_promotions
                )
                """
            ).fetchall()
        )

        target_column = next(
            row
            for row in column_rows
            if row[1]
            == "target_subdirectory"
        )

        assert target_column[2] == "TEXT"
        assert target_column[3] == 1
        assert target_column[4] == "'.'"

    finally:
        connection.close()