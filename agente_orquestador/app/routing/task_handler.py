from __future__ import annotations

from dataclasses import dataclass

from app.routing.models import (
    RequestKind,
    RoutingDecision,
)
from app.tasks.models import (
    TaskRecord,
    TaskStatus,
)


@dataclass(frozen=True, slots=True)
class TaskHandlingResult:
    text: str
    status: str
    project_name: str | None


class ProvisionalTaskHandler:
    _STATUS_LABELS = {
        TaskStatus.PENDING_CLARIFICATION: (
            "pendiente de aclaraciones"
        ),
        TaskStatus.PENDING_PLANNING: (
            "pendiente de planificación"
        ),
        TaskStatus.PENDING_APPROVAL: (
            "pendiente de autorización"
        ),
        TaskStatus.APPROVED: "autorizada",
        TaskStatus.CANCELLED: "cancelada",
        TaskStatus.IN_PROGRESS: "en ejecución",
        TaskStatus.COMPLETED: "completada",
        TaskStatus.FAILED: "fallida",
    }

    def handle(
        self,
        decision: RoutingDecision,
        task: TaskRecord,
    ) -> TaskHandlingResult:
        if decision.kind != RequestKind.TASK:
            raise ValueError(
                "ProvisionalTaskHandler solamente "
                "acepta peticiones de tipo task"
            )

        project_name = (
            task.target_project_name
            or decision.project_name
            or "Sin determinar"
        )

        status_label = self._STATUS_LABELS[
            task.status
        ]

        lines = [
            "PETICIÓN IDENTIFICADA COMO TAREA",
            "",
            f"Resumen: {task.description}",
            f"Proyecto: {project_name}",
            (
                "Confianza: "
                f"{decision.confidence:.0%}"
            ),
            f"Estado: {status_label}",
        ]

        if task.missing_information:
            lines.extend(
                [
                    "",
                    "Necesito que aclares:",
                ]
            )

            for index, question in enumerate(
                task.missing_information,
                start=1,
            ):
                lines.append(
                    f"{index}. {question}"
                )

        lines.extend(
            [
                "",
                (
                    "No se ha ejecutado ningún "
                    "cambio. La tarea deberá ser "
                    "planificada y autorizada "
                    "antes de comenzar."
                ),
            ]
        )

        return TaskHandlingResult(
            text="\n".join(lines),
            status=task.status.value,
            project_name=(
                task.target_project_name
            ),
        )