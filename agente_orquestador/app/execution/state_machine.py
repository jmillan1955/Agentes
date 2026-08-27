from __future__ import annotations

from app.execution.models import (
    ExecutionStatus,
    ExecutionStepStatus,
)


class InvalidExecutionTransitionError(
    ValueError
):
    """Transicion de ejecucion no permitida."""


class ExecutionStateMachine:
    _TRANSITIONS = {
        ExecutionStatus.PREPARED: {
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
        },
        ExecutionStatus.RUNNING: {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
            ExecutionStatus.CANCELLED,
        },
        ExecutionStatus.FAILED: {
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
        },
        ExecutionStatus.INTERRUPTED: {
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
        },
        ExecutionStatus.COMPLETED: set(),
        ExecutionStatus.CANCELLED: set(),
    }

    def can_transition(
        self,
        current_status: ExecutionStatus,
        target_status: ExecutionStatus,
    ) -> bool:
        return (
            target_status
            in self._TRANSITIONS[
                current_status
            ]
        )

    def validate_transition(
        self,
        current_status: ExecutionStatus,
        target_status: ExecutionStatus,
    ) -> None:
        if self.can_transition(
            current_status=current_status,
            target_status=target_status,
        ):
            return

        raise InvalidExecutionTransitionError(
            "No se permite cambiar una "
            "ejecucion "
            f"de '{current_status.value}' "
            f"a '{target_status.value}'"
        )

    def allowed_targets(
        self,
        current_status: ExecutionStatus,
    ) -> tuple[ExecutionStatus, ...]:
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

class InvalidExecutionStepTransitionError(
        ValueError
    ):
        """Transicion de paso no permitida."""


class ExecutionStepStateMachine:
    _TRANSITIONS = {
        ExecutionStepStatus.PENDING: {
            ExecutionStepStatus.RUNNING,
            ExecutionStepStatus.SKIPPED,
            ExecutionStepStatus.CANCELLED,
        },
        ExecutionStepStatus.RUNNING: {
            ExecutionStepStatus.COMPLETED,
            ExecutionStepStatus.FAILED,
            ExecutionStepStatus.CANCELLED,
        },
        ExecutionStepStatus.COMPLETED: set(),
        ExecutionStepStatus.FAILED: set(),
        ExecutionStepStatus.SKIPPED: set(),
        ExecutionStepStatus.CANCELLED: set(),
    }

    def can_transition(
        self,
        current_status: ExecutionStepStatus,
        target_status: ExecutionStepStatus,
    ) -> bool:
        return (
            target_status
            in self._TRANSITIONS[
                current_status
            ]
        )

    def validate_transition(
        self,
        current_status: ExecutionStepStatus,
        target_status: ExecutionStepStatus,
    ) -> None:
        if self.can_transition(
            current_status=current_status,
            target_status=target_status,
        ):
            return

        raise InvalidExecutionStepTransitionError(
            "No se permite cambiar un paso "
            f"de '{current_status.value}' "
            f"a '{target_status.value}'"
        )