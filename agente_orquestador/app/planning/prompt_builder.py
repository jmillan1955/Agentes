from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from app.tasks import (
    TaskClarificationResponse,
    TaskRecord,
)


PLANNING_SYSTEM_PROMPT = (
    "Eres el planificador técnico del Agente "
    "Orquestador de José. "
    "Tu función es transformar una petición de "
    "proyecto en una primera planificación útil. "
    "Debes proponer tecnologías, arquitectura, "
    "interfaces, entradas, salidas, datos, fases "
    "de trabajo, pruebas y despliegue. "
    "Puedes proponer decisiones razonables cuando "
    "el usuario todavía no las haya indicado. "
    "Las suposiciones importantes deben aparecer "
    "como decisiones pendientes. "
    "No escribas código y no indiques que has "
    "creado o modificado archivos. "
    "Devuelve exclusivamente un objeto JSON válido. "
    "No utilices bloques Markdown ni explicaciones "
    "fuera del JSON. "
    "No muestres razonamientos internos."
)


@dataclass(frozen=True, slots=True)
class PlanningPromptPackage:
    system_prompt: str
    user_prompt: str


class PlanningPromptBuilder:
    def __init__(
        self,
        system_prompt: str = (
            PLANNING_SYSTEM_PROMPT
        ),
    ) -> None:
        clean_system_prompt = (
            system_prompt.strip()
        )

        if not clean_system_prompt:
            raise ValueError(
                "system_prompt no puede "
                "estar vacío"
            )

        self._system_prompt = (
            clean_system_prompt
        )

    def build(
        self,
        task: TaskRecord,
        clarification_responses: Iterable[
            TaskClarificationResponse
        ] = (),
    ) -> PlanningPromptPackage:
        responses = tuple(
            clarification_responses
        )

        lines = [
            "TAREA QUE DEBE PLANIFICARSE",
            "",
            f"Identificador: {task.id}",
            f"Título: {task.title}",
            (
                "Proyecto objetivo: "
                f"{task.target_project_name or 'Sin determinar'}"
            ),
            "",
            "DESCRIPCIÓN INICIAL",
            task.description,
            "",
            "ACLARACIONES DEL USUARIO",
        ]

        if not responses:
            lines.append(
                "No hay aclaraciones adicionales."
            )

        else:
            for index, response in enumerate(
                responses,
                start=1,
            ):
                lines.extend(
                    [
                        "",
                        f"Aclaración {index}",
                        "Preguntas realizadas:",
                    ]
                )

                for question in response.questions:
                    lines.append(
                        f"- {question}"
                    )

                lines.extend(
                    [
                        "Respuesta del usuario:",
                        response.answer,
                    ]
                )

        lines.extend(
            [
                "",
                "INSTRUCCIONES DE PLANIFICACIÓN",
                (
                    "Genera una primera planificación "
                    "aunque todavía existan decisiones "
                    "pendientes."
                ),
                (
                    "Selecciona tecnologías concretas "
                    "y adecuadas para el proyecto."
                ),
                (
                    "Indica expresamente las interfaces, "
                    "entradas y salidas."
                ),
                (
                    "Utiliza las aclaraciones como "
                    "información confirmada."
                ),
                (
                    "No vuelvas a preguntar aquello que "
                    "el usuario ya haya respondido."
                ),
                (
                    "Incluye en pending_decisions las "
                    "decisiones importantes que todavía "
                    "necesiten confirmación."
                ),
                (
                    "No incluyas preguntas innecesarias "
                    "que no bloqueen ni modifiquen el "
                    "diseño del proyecto."
                ),
                (
                    "No escribas código ni ejecutes "
                    "ningún cambio."
                ),
                "",
                "FORMATO DE SALIDA OBLIGATORIO",
                "{",
                '  "objective": "texto",',
                '  "scope": ["texto"],',
                '  "technologies": ["texto"],',
                '  "interfaces": ["texto"],',
                '  "inputs": ["texto"],',
                '  "outputs": ["texto"],',
                '  "data_entities": ["texto"],',
                '  "business_rules": ["texto"],',
                '  "phases": ["texto"],',
                '  "tests": ["texto"],',
                '  "deployment": ["texto"],',
                (
                    '  "pending_decisions": '
                    '["texto"],'
                ),
                '  "excluded_items": ["texto"],',
                (
                    '  "completion_criteria": '
                    '["texto"]'
                ),
                "}",
                "",
                (
                    "Todos los campos son obligatorios. "
                    "Los campos distintos de objective "
                    "deben ser listas JSON de textos."
                ),
            ]
        )

        return PlanningPromptPackage(
            system_prompt=self._system_prompt,
            user_prompt="\n".join(lines),
        )