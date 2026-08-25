from __future__ import annotations

from dataclasses import dataclass

from app.context.task_clarification_response_repository import (
    TaskClarificationResponseRepository,
)
from app.context.task_repository import (
    TaskRepository,
)
from app.planning.service import (
    GeneratedPlan,
    PlanningService,
)
from app.tasks.clarification_response import (
    TaskClarificationResponse,
)
from app.tasks.models import (
    TaskRecord,
    TaskStatus,
)


@dataclass(frozen=True, slots=True)
class ClarificationWorkflowResult:
    task: TaskRecord
    clarification: TaskClarificationResponse
    generated_plan: GeneratedPlan


class ClarificationWorkflowService:
    def __init__(
        self,
        task_repository: TaskRepository,
        clarification_repository: (
            TaskClarificationResponseRepository
        ),
        planning_service: PlanningService,
    ) -> None:
        self._task_repository = task_repository
        self._clarification_repository = (
            clarification_repository
        )
        self._planning_service = (
            planning_service
        )

    def respond(
        self,
        task_id: int,
        session_id: int,
        response_message_id: str,
        answer: str,
    ) -> ClarificationWorkflowResult:
        task = self._task_repository.get_by_id(
            task_id
        )

        if task is None:
            raise ValueError(
                f"No existe la tarea #{task_id}"
            )

        if task.session_id != session_id:
            raise ValueError(
                "La tarea no pertenece a "
                "esta conversación"
            )

        if (
            task.status
            != TaskStatus.PENDING_CLARIFICATION
        ):
            raise ValueError(
                "La tarea no está pendiente "
                "de aclaración"
            )

        if not task.missing_information:
            raise ValueError(
                "La tarea no tiene preguntas "
                "pendientes"
            )

        clarification = (
            self._clarification_repository.create(
                task_id=task.id,
                response_message_id=(
                    response_message_id
                ),
                questions=(
                    task.missing_information
                ),
                answer=answer,
            )
        )

        generated_plan = (
            self._planning_service.generate(
                task.id
            )
        )

        task = (
            self._task_repository
            .return_to_planning(task.id)
        )

        if (
            generated_plan.plan
            .pending_decisions
        ):
            task = (
                self._task_repository
                .set_missing_information(
                    task_id=task.id,
                    missing_information=(
                        generated_plan.plan
                        .pending_decisions
                    ),
                )
            )

        else:
            task = self._task_repository.set_plan(
                task_id=task.id,
                plan=generated_plan.plan.phases,
            )

        return ClarificationWorkflowResult(
            task=task,
            clarification=clarification,
            generated_plan=generated_plan,
        )