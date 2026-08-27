from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 8


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


CREATE TABLE IF NOT EXISTS task_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    plan_version INTEGER NOT NULL
        CHECK (plan_version > 0),
    authorized_user_id TEXT NOT NULL,
    authorization_message_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    FOREIGN KEY (plan_id)
        REFERENCES task_plans(id)
        ON DELETE CASCADE,
    UNIQUE (task_id),
    UNIQUE (plan_id),
    UNIQUE (
        channel,
        authorization_message_id
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

CREATE TABLE IF NOT EXISTS task_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    approval_id INTEGER NOT NULL,
    status TEXT NOT NULL
        DEFAULT 'prepared'
        CHECK (
            status IN (
                'prepared',
                'running',
                'completed',
                'failed',
                'interrupted',
                'cancelled'
            )
        ),
    workspace_path TEXT NOT NULL,
    requested_by_user_id TEXT NOT NULL,
    request_message_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    attempt_count INTEGER NOT NULL
        DEFAULT 0
        CHECK (attempt_count >= 0),
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    started_at TEXT,
    finished_at TEXT,
    last_error TEXT,
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    FOREIGN KEY (plan_id)
        REFERENCES task_plans(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (approval_id)
        REFERENCES task_approvals(id)
        ON DELETE RESTRICT,
    UNIQUE (task_id),
    UNIQUE (approval_id),
    UNIQUE (
        channel,
        request_message_id
    )
);

CREATE TABLE IF NOT EXISTS
task_execution_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    version INTEGER NOT NULL
        CHECK (version > 0),
    status TEXT NOT NULL
        DEFAULT 'draft'
        CHECK (
            status IN (
                'draft',
                'pending_confirmation',
                'confirmed',
                'superseded'
            )
        ),
    manifest_hash TEXT NOT NULL
        CHECK (length(manifest_hash) = 64),
    action_count INTEGER NOT NULL
        CHECK (action_count > 0),
    destructive_action_count INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            destructive_action_count >= 0
            AND destructive_action_count
                <= action_count
        ),
    created_at TEXT NOT NULL DEFAULT (
        strftime(
            '%Y-%m-%dT%H:%M:%fZ',
            'now'
        )
    ),
    confirmed_at TEXT,
    confirmed_by_user_id TEXT,
    confirmation_message_id TEXT,
    confirmation_channel TEXT,
    FOREIGN KEY (execution_id)
        REFERENCES task_executions(id)
        ON DELETE CASCADE,
    UNIQUE (
        execution_id,
        version
    ),
    UNIQUE (
        confirmation_channel,
        confirmation_message_id
    )
);

CREATE TABLE IF NOT EXISTS
task_execution_manifest_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL
        CHECK (step_number > 0),
    name TEXT NOT NULL,
    action_type TEXT NOT NULL
        CHECK (
            action_type IN (
                'create_directory',
                'write_text_file',
                'run_pytest'
            )
        ),
    relative_path TEXT NOT NULL,
    content_text TEXT,
    content_sha256 TEXT
        CHECK (
            content_sha256 IS NULL
            OR length(content_sha256) = 64
        ),
    destructive INTEGER NOT NULL
        DEFAULT 0
        CHECK (destructive IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (
        strftime(
            '%Y-%m-%dT%H:%M:%fZ',
            'now'
        )
    ),
    FOREIGN KEY (manifest_id)
        REFERENCES task_execution_manifests(id)
        ON DELETE CASCADE,
    UNIQUE (
        manifest_id,
        step_number
    )
);

CREATE TABLE IF NOT EXISTS
task_execution_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL
        CHECK (attempt_number > 0),
    status TEXT NOT NULL
        DEFAULT 'running'
        CHECK (
            status IN (
                'running',
                'completed',
                'failed',
                'interrupted',
                'cancelled'
            )
        ),
    started_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    finished_at TEXT,
    exit_code INTEGER,
    error_message TEXT,
    FOREIGN KEY (execution_id)
        REFERENCES task_executions(id)
        ON DELETE CASCADE,
    UNIQUE (
        execution_id,
        attempt_number
    )
);

CREATE TABLE IF NOT EXISTS
task_execution_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL
        CHECK (step_number > 0),
    name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL
        DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'running',
                'completed',
                'failed',
                'skipped',
                'cancelled'
            )
        ),
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    stdout_text TEXT,
    stderr_text TEXT,
    error_message TEXT,
    FOREIGN KEY (attempt_id)
        REFERENCES task_execution_attempts(id)
        ON DELETE CASCADE,
    UNIQUE (
        attempt_id,
        step_number
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
idx_task_approvals_user
ON task_approvals(
    authorized_user_id,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_task_executions_status
ON task_executions(
    status,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_task_executions_plan
ON task_executions(
    plan_id,
    created_at
);

CREATE INDEX IF NOT EXISTS
idx_execution_attempts_execution
ON task_execution_attempts(
    execution_id,
    attempt_number
);

CREATE INDEX IF NOT EXISTS
idx_execution_attempts_status
ON task_execution_attempts(
    status,
    started_at
);

CREATE INDEX IF NOT EXISTS
idx_execution_steps_attempt
ON task_execution_steps(
    attempt_id,
    step_number
);

CREATE INDEX IF NOT EXISTS
idx_execution_steps_status
ON task_execution_steps(
    status,
    started_at
);

CREATE INDEX IF NOT EXISTS
idx_execution_manifests_execution
ON task_execution_manifests(
    execution_id,
    version
);

CREATE INDEX IF NOT EXISTS
idx_manifest_actions_manifest
ON task_execution_manifest_actions(
    manifest_id,
    step_number
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