from __future__ import annotations

from app.approvals.service import (
    ApprovalResult,
    CancellationResult,
)

class ApprovalFormatter:
    def format(
        self,
        result: ApprovalResult,
    ) -> str:
        project_name = (
            result.task.target_project_name
            or "Sin determinar"
        )

        title = (
            "PLAN YA APROBADO"
            if result.already_approved
            else "PLAN APROBADO"
        )

        lines = [
            title,
            "",
            f"Tarea: #{result.task.id}",
            f"Proyecto: {project_name}",
            (
                "Plan aprobado: version "
                f"{result.plan.version}"
            ),
            (
                "Usuario aprobador: "
                f"{result.approval.authorized_user_id}"
            ),
            (
                "Fecha de aprobacion: "
                f"{result.approval.created_at}"
            ),
            "",
        ]

        if result.already_approved:
            lines.extend(
                [
                    (
                        "La tarea ya estaba "
                        "autorizada anteriormente."
                    ),
                    (
                        "Se conserva la autorizacion "
                        "original."
                    ),
                ]
            )

        else:
            lines.extend(
                [
                    (
                        "La autorizacion ha quedado "
                        "registrada correctamente."
                    ),
                    (
                        "La tarea queda preparada "
                        "para una futura ejecucion "
                        "controlada."
                    ),
                ]
            )

        lines.extend(
            [
                "",
                (
                    "No se ha creado ni modificado "
                    "codigo del proyecto."
                ),
            ]
        )

        return "\n".join(lines)

    def format_cancellation(
        self,
        result: CancellationResult,
    ) -> str:
        project_name = (
            result.task.target_project_name
            or "Sin determinar"
        )

        if result.already_cancelled:
            title = "TAREA YA CANCELADA"
            status_message = (
                "La tarea ya estaba cancelada."
            )
        else:
            title = "TAREA APROBADA CANCELADA"
            status_message = (
                "La tarea aprobada ha sido "
                "cancelada correctamente."
            )

        return "\n".join(
            [
                title,
                "",
                f"Tarea: #{result.task.id}",
                f"Proyecto: {project_name}",
                (
                    "Plan aprobado conservado: "
                    f"version {result.plan.version}"
                ),
                (
                    "Cancelada por: "
                    f"{result.cancelled_user_id}"
                ),
                "",
                status_message,
                (
                    "La autorizacion se conserva "
                    "como historial."
                ),
                (
                    "La tarea no podra iniciar "
                    "su ejecucion."
                ),
                "",
                (
                    "No se ha creado ni modificado "
                    "codigo del proyecto."
                ),
            ]
        )