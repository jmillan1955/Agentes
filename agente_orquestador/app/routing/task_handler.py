from __future__ import annotations

from dataclasses import dataclass

from app.routing.models import (
    RequestKind,
    RoutingDecision,
)


@dataclass(frozen=True, slots=True)
class TaskHandlingResult:
    text: str
    status: str
    project_name: str | None


class ProvisionalTaskHandler:
    def handle(
        self,
        decision: RoutingDecision,
    ) -> TaskHandlingResult:
        if decision.kind != RequestKind.TASK:
            raise ValueError(
                "ProvisionalTaskHandler solamente "
                "acepta peticiones de tipo task"
            )

        project_name = (
            decision.project_name
            or "Sin determinar"
        )

        lines = [
            "PETICIÓN IDENTIFICADA COMO TAREA",
            "",
            f"Resumen: {decision.summary}",
            f"Proyecto: {project_name}",
            (
                "Confianza: "
                f"{decision.confidence:.0%}"
            ),
            "Estado: pendiente de planificación",
            "",
            (
                "No se ha ejecutado ningún cambio. "
                "La tarea deberá ser planificada "
                "y autorizada antes de comenzar."
            ),
        ]

        return TaskHandlingResult(
            text="\n".join(lines),
            status="pending_planning",
            project_name=decision.project_name,
        )