from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 1


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    root_path TEXT NOT NULL,
    git_repository TEXT,
    active INTEGER NOT NULL DEFAULT 1
        CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    updated_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    )
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    channel TEXT NOT NULL,
    user_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    ended_at TEXT,
    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    message_id TEXT NOT NULL,
    correlation_id TEXT,
    direction TEXT NOT NULL
        CHECK (direction IN ('incoming', 'outgoing')),
    channel TEXT NOT NULL,
    content_type TEXT NOT NULL,
    text TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (session_id)
        REFERENCES sessions(id)
        ON DELETE CASCADE,
    UNIQUE (channel, message_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_modified_at TEXT,
    synchronized_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    git_commit_hash TEXT,
    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE,
    UNIQUE (project_id, relative_path)
);

CREATE TABLE IF NOT EXISTS git_commits (
    commit_hash TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    parent_hash TEXT,
    author_name TEXT,
    authored_at TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT,
    synchronized_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_conversation
ON sessions(channel, conversation_id);

CREATE INDEX IF NOT EXISTS idx_messages_session
ON messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_documents_project
ON documents(project_id, relative_path);

CREATE INDEX IF NOT EXISTS idx_git_commits_project
ON git_commits(project_id, authored_at);
"""


def initialize_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.execute(
        f"PRAGMA user_version = {SCHEMA_VERSION}"
    )
    connection.commit()