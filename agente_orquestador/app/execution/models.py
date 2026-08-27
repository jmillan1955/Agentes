from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionStatus(str, Enum):
    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TaskExecution:
    id: int
    task_id: int
    plan_id: int
    approval_id: int
    status: ExecutionStatus
    workspace_path: str
    requested_by_user_id: str
    request_message_id: str
    channel: str
    attempt_count: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    last_error: str | None

    def __post_init__(self) -> None:
        integer_fields = (
            "id",
            "task_id",
            "plan_id",
            "approval_id",
        )

        for field_name in integer_fields:
            value = getattr(
                self,
                field_name,
            )

            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero"
                )

        if self.attempt_count < 0:
            raise ValueError(
                "attempt_count no puede ser "
                "negativo"
            )

        text_fields = (
            "workspace_path",
            "requested_by_user_id",
            "request_message_id",
            "channel",
            "created_at",
        )

        for field_name in text_fields:
            value = getattr(
                self,
                field_name,
            ).strip()

            if not value:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        optional_text_fields = (
            "started_at",
            "finished_at",
            "last_error",
        )

        for field_name in optional_text_fields:
            value = getattr(
                self,
                field_name,
            )

            if value is None:
                continue

            normalized = value.strip()

            object.__setattr__(
                self,
                field_name,
                normalized or None,
            )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.CANCELLED,
        }

    @property
    def can_resume(self) -> bool:
        return self.status in {
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
        }

class ExecutionAttemptStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"

class ExecutionStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    id: int
    execution_id: int
    attempt_number: int
    status: ExecutionAttemptStatus
    started_at: str
    finished_at: str | None
    exit_code: int | None
    error_message: str | None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        if self.attempt_number <= 0:
            raise ValueError(
                "attempt_number debe ser "
                "mayor que cero"
            )

        started_at = self.started_at.strip()

        if not started_at:
            raise ValueError(
                "started_at no puede estar vacio"
            )

        object.__setattr__(
            self,
            "started_at",
            started_at,
        )

        for field_name in (
            "finished_at",
            "error_message",
        ):
            value = getattr(
                self,
                field_name,
            )

            if value is None:
                continue

            normalized = value.strip()

            object.__setattr__(
                self,
                field_name,
                normalized or None,
            )

    @property
    def is_terminal(self) -> bool:
        return (
            self.status
            != ExecutionAttemptStatus.RUNNING
        )

@dataclass(frozen=True, slots=True)
class ExecutionStep:
    id: int
    attempt_id: int
    step_number: int
    name: str
    action_type: str
    status: ExecutionStepStatus
    started_at: str | None
    finished_at: str | None
    exit_code: int | None
    stdout_text: str | None
    stderr_text: str | None
    error_message: str | None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.attempt_id <= 0:
            raise ValueError(
                "attempt_id debe ser "
                "mayor que cero"
            )

        if self.step_number <= 0:
            raise ValueError(
                "step_number debe ser "
                "mayor que cero"
            )

        for field_name in (
            "name",
            "action_type",
        ):
            value = getattr(
                self,
                field_name,
            ).strip()

            if not value:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        for field_name in (
            "started_at",
            "finished_at",
            "stdout_text",
            "stderr_text",
            "error_message",
        ):
            value = getattr(
                self,
                field_name,
            )

            if value is None:
                continue

            normalized = value.strip()

            object.__setattr__(
                self,
                field_name,
                normalized or None,
            )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ExecutionStepStatus.COMPLETED,
            ExecutionStepStatus.FAILED,
            ExecutionStepStatus.SKIPPED,
            ExecutionStepStatus.CANCELLED,
        }