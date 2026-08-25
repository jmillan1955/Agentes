from __future__ import annotations

from app.planning.models import (
    PlanStatus,
    TaskPlan,
)
from app.tasks.models import TaskRecord


class PlanningFormatter:
    _STATUS_LABELS = {
        PlanStatus.DRAFT: "borrador",
        PlanStatus.PENDING_CLARIFICATION: (
            "pendiente de aclaraciones"
        ),
        PlanStatus.PENDING_APPROVAL: (
            "pendiente de aprobación"
        ),
        PlanStatus.APPROVED: "aprobado",
        PlanStatus.SUPERSEDED: "sustituido",
    }

    def format(
        self,
        plan: TaskPlan,
        task: TaskRecord,
    ) -> str:
        project_name = (
            task.target_project_name
            or "Sin determinar"
        )

        lines = [
            (
                "PLAN PROPUESTO — "
                f"VERSIÓN {plan.version}"
            ),
            "",
            f"Tarea: #{task.id}",
            f"Proyecto: {project_name}",
            (
                "Estado del plan: "
                f"{self._STATUS_LABELS[plan.status]}"
            ),
            "",
            "OBJETIVO",
            plan.objective,
        ]

        self._append_section(
            lines=lines,
            title="ALCANCE FUNCIONAL",
            values=plan.scope,
        )

        self._append_section(
            lines=lines,
            title="TECNOLOGÍAS PROPUESTAS",
            values=plan.technologies,
        )

        self._append_section(
            lines=lines,
            title="INTERFACES",
            values=plan.interfaces,
        )

        self._append_section(
            lines=lines,
            title="ENTRADAS",
            values=plan.inputs,
        )

        self._append_section(
            lines=lines,
            title="SALIDAS",
            values=plan.outputs,
        )

        self._append_section(
            lines=lines,
            title="ENTIDADES DE DATOS",
            values=plan.data_entities,
        )

        self._append_section(
            lines=lines,
            title="REGLAS DE NEGOCIO",
            values=plan.business_rules,
        )

        self._append_section(
            lines=lines,
            title="FASES DE CONSTRUCCIÓN",
            values=plan.phases,
            numbered=True,
        )

        self._append_section(
            lines=lines,
            title="PRUEBAS PREVISTAS",
            values=plan.tests,
        )

        self._append_section(
            lines=lines,
            title="DESPLIEGUE",
            values=plan.deployment,
        )

        self._append_section(
            lines=lines,
            title="ELEMENTOS EXCLUIDOS",
            values=plan.excluded_items,
        )

        self._append_section(
            lines=lines,
            title="CRITERIOS DE FINALIZACIÓN",
            values=plan.completion_criteria,
        )

        if plan.pending_decisions:
            self._append_section(
                lines=lines,
                title="DECISIONES PENDIENTES",
                values=plan.pending_decisions,
                numbered=True,
            )

            lines.extend(
                [
                    "",
                    (
                        "Responde mediante:"
                    ),
                    (
                        f"/responder {task.id} "
                        "<tus aclaraciones>"
                    ),
                ]
            )

        else:
            lines.extend(
                [
                    "",
                    (
                        "La planificación no tiene "
                        "decisiones bloqueantes."
                    ),
                    (
                        "La tarea está preparada "
                        "para solicitar aprobación."
                    ),
                ]
            )

        lines.extend(
            [
                "",
                (
                    "No se ha creado ni modificado "
                    "código del proyecto."
                ),
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def _append_section(
        lines: list[str],
        title: str,
        values: tuple[str, ...],
        numbered: bool = False,
    ) -> None:
        if not values:
            return

        lines.extend(
            [
                "",
                title,
            ]
        )

        for index, value in enumerate(
            values,
            start=1,
        ):
            prefix = (
                f"{index}."
                if numbered
                else "-"
            )

            lines.append(
                f"{prefix} {value}"
            )