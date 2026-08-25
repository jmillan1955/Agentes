from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskStatus(str, Enum):
    PENDING_CLARIFICATION = (
        "pending_clarification"
    )
    PENDING_PLANNING = "pending_planning"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskRecord:
    id: int
    project_id: int
    session_id: int
    source_message_id: str
    title: str
    description: str
    target_project_name: str | None
    status: TaskStatus
    missing_information: tuple[str, ...]
    plan: tuple[str, ...]
    created_at: str
    updated_at: str
    authorized_at: str | None
    completed_at: str | None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.project_id <= 0:
            raise ValueError(
                "project_id debe ser "
                "mayor que cero"
            )

        if self.session_id <= 0:
            raise ValueError(
                "session_id debe ser "
                "mayor que cero"
            )

        source_message_id = (
            self.source_message_id.strip()
        )
        title = self.title.strip()
        description = self.description.strip()

        if not source_message_id:
            raise ValueError(
                "source_message_id no puede "
                "estar vacío"
            )

        if not title:
            raise ValueError(
                "title no puede estar vacío"
            )

        if not description:
            raise ValueError(
                "description no puede "
                "estar vacía"
            )

        target_project_name = (
            self.target_project_name.strip()
            if self.target_project_name
            is not None
            else None
        )

        missing_information = tuple(
            value.strip()
            for value in self.missing_information
            if value.strip()
        )

        plan = tuple(
            step.strip()
            for step in self.plan
            if step.strip()
        )

        object.__setattr__(
            self,
            "source_message_id",
            source_message_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "description",
            description,
        )
        object.__setattr__(
            self,
            "target_project_name",
            target_project_name or None,
        )
        object.__setattr__(
            self,
            "missing_information",
            missing_information,
        )
        object.__setattr__(
            self,
            "plan",
            plan,
        )

    @property
    def requires_clarification(self) -> bool:
        return (
            self.status
            == TaskStatus.PENDING_CLARIFICATION
            or bool(self.missing_information)
        )

    @property
    def requires_approval(self) -> bool:
        return (
            self.status
            == TaskStatus.PENDING_APPROVAL
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.CANCELLED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
        }