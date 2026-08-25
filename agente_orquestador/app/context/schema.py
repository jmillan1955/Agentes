from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 5


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
        CHECK (
            direction IN (
                'incoming',
                'outgoing'
            )
        ),
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

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    source_message_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_project_name TEXT,
    status TEXT NOT NULL
        DEFAULT 'pending_planning'
        CHECK (
            status IN (
                'pending_clarification',
                'pending_planning',
                'pending_approval',
                'approved',
                'cancelled',
                'in_progress',
                'completed',
                'failed'
            )
        ),
    missing_information_json TEXT
        NOT NULL DEFAULT '[]',
    plan_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    updated_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    authorized_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE,
    FOREIGN KEY (session_id)
        REFERENCES sessions(id)
        ON DELETE CASCADE,
    UNIQUE (
        session_id,
        source_message_id
    )
);

CREATE TABLE IF NOT EXISTS
task_clarification_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    response_message_id TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    UNIQUE (
        task_id,
        response_message_id
    )
);

CREATE TABLE IF NOT EXISTS task_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    version INTEGER NOT NULL
        CHECK (version > 0),
    status TEXT NOT NULL
        DEFAULT 'draft'
        CHECK (
            status IN (
                'draft',
                'pending_clarification',
                'pending_approval',
                'approved',
                'superseded'
            )
        ),
    objective TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '[]',
    technologies_json TEXT
        NOT NULL DEFAULT '[]',
    interfaces_json TEXT NOT NULL DEFAULT '[]',
    inputs_json TEXT NOT NULL DEFAULT '[]',
    outputs_json TEXT NOT NULL DEFAULT '[]',
    data_entities_json TEXT
        NOT NULL DEFAULT '[]',
    business_rules_json TEXT
        NOT NULL DEFAULT '[]',
    phases_json TEXT NOT NULL DEFAULT '[]',
    tests_json TEXT NOT NULL DEFAULT '[]',
    deployment_json TEXT NOT NULL DEFAULT '[]',
    pending_decisions_json TEXT
        NOT NULL DEFAULT '[]',
    excluded_items_json TEXT
        NOT NULL DEFAULT '[]',
    completion_criteria_json TEXT
        NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    updated_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    UNIQUE (
        task_id,
        version
    )
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
    UNIQUE (
        project_id,
        relative_path
    )
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

CREATE INDEX IF NOT EXISTS
idx_sessions_conversation
ON sessions(
    channel,
    conversation_id
);

CREATE UNIQUE INDEX IF NOT EXISTS
idx_sessions_active_unique
ON sessions(
    project_id,
    channel,
    user_id,
    conversation_id
)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS
idx_messages_session
ON messages(
    session_id,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_tasks_project_status
ON tasks(
    project_id,
    status,
    updated_at
);

CREATE INDEX IF NOT EXISTS
idx_tasks_session
ON tasks(
    session_id,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_tasks_target_project
ON tasks(
    target_project_name,
    status
);

CREATE INDEX IF NOT EXISTS
idx_task_clarifications_task
ON task_clarification_responses(
    task_id,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_task_plans_task_version
ON task_plans(
    task_id,
    version
);

CREATE INDEX IF NOT EXISTS
idx_task_plans_task_status
ON task_plans(
    task_id,
    status,
    updated_at
);

CREATE INDEX IF NOT EXISTS
idx_documents_project
ON documents(
    project_id,
    relative_path
);

CREATE INDEX IF NOT EXISTS
idx_git_commits_project
ON git_commits(
    project_id,
    authored_at
);
"""


def initialize_schema(
    connection: sqlite3.Connection,
) -> None:
    current_version = connection.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    if current_version > SCHEMA_VERSION:
        raise RuntimeError(
            "La base de datos utiliza una "
            "versión de esquema más reciente"
        )

    connection.executescript(SCHEMA_SQL)

    connection.execute(
        f"PRAGMA user_version = {SCHEMA_VERSION}"
    )

    connection.commit()