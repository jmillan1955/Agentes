from __future__ import annotations

from dataclasses import dataclass


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