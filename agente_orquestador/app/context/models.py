from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    id: int
    name: str
    root_path: str
    git_repository: str | None
    active: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: int
    project_id: int | None
    channel: str
    user_id: str
    conversation_id: str
    status: str
    started_at: str
    ended_at: str | None


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: int
    session_id: int
    message_id: str
    correlation_id: str | None
    direction: str
    channel: str
    content_type: str
    text: str | None
    metadata: dict[str, Any]
    created_at: str

@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: int
    project_id: int
    relative_path: str
    title: str | None
    content: str
    content_hash: str
    file_modified_at: str | None
    synchronized_at: str
    git_commit_hash: str | None