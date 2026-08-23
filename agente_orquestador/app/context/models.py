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

@dataclass(frozen=True, slots=True)
class GitCommitRecord:
    commit_hash: str
    project_id: int
    parent_hash: str | None
    author_name: str | None
    authored_at: str
    subject: str
    body: str | None
    synchronized_at: str

@dataclass(frozen=True, slots=True)
class ContextDocumentSummary:
    relative_path: str
    title: str | None
    synchronized_at: str


@dataclass(frozen=True, slots=True)
class ContextCommitSummary:
    commit_hash: str
    subject: str
    authored_at: str


@dataclass(frozen=True, slots=True)
class ContextSummary:
    project_id: int
    project_name: str
    total_sessions: int
    active_sessions: int
    total_messages: int
    total_documents: int
    total_commits: int
    recent_documents: tuple[
        ContextDocumentSummary,
        ...,
    ]
    recent_commits: tuple[
        ContextCommitSummary,
        ...,
    ]

@dataclass(frozen=True, slots=True)
class ContextDocumentMatch:
    document_id: int
    relative_path: str
    title: str | None
    score: int
    matched_terms: tuple[str, ...]
    excerpt: str


@dataclass(frozen=True, slots=True)
class ContextSearchResult:
    query: str
    terms: tuple[str, ...]
    documents: tuple[
        ContextDocumentMatch,
        ...,
    ]