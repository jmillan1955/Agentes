from __future__ import annotations

from app.tasks.models import TaskStatus


class InvalidTaskTransitionError(
    ValueError
):
    """Transición de tarea no permitida."""


class TaskStateMachine:
    _TRANSITIONS = {
        TaskStatus.PENDING_PLANNING: {
            TaskStatus.PENDING_CLARIFICATION,
            TaskStatus.PENDING_APPROVAL,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.PENDING_CLARIFICATION: {
            TaskStatus.PENDING_PLANNING,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.PENDING_APPROVAL: {
            TaskStatus.APPROVED,
            TaskStatus.CANCELLED,
            TaskStatus.PENDING_PLANNING,
        },
        TaskStatus.APPROVED: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.CANCELLED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.FAILED: set(),
        TaskStatus.CANCELLED: set(),
    }

    def can_transition(
        self,
        current_status: TaskStatus,
        target_status: TaskStatus,
    ) -> bool:
        return (
            target_status
            in self._TRANSITIONS[
                current_status
            ]
        )

    def validate_transition(
        self,
        current_status: TaskStatus,
        target_status: TaskStatus,
    ) -> None:
        if self.can_transition(
            current_status=current_status,
            target_status=target_status,
        ):
            return

        raise InvalidTaskTransitionError(
            "No se permite cambiar una tarea "
            f"de '{current_status.value}' "
            f"a '{target_status.value}'"
        )

    def allowed_targets(
        self,
        current_status: TaskStatus,
    ) -> tuple[TaskStatus, ...]:
        return tuple(
            sorted(
                self._TRANSITIONS[
                    current_status
                ],
                key=lambda status: (
                    status.value
                ),
            )
        )