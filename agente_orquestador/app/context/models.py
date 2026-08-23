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