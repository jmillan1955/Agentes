from __future__ import annotations

from dataclasses import dataclass

from app.context import ContextBlock


DEFAULT_SYSTEM_PROMPT = (
    "Eres el Agente Orquestador de José. "
    "Responde siempre en español, con claridad "
    "y de forma práctica y directa. "
    "No muestres razonamientos internos. "
    "Utiliza el contexto recuperado cuando la "
    "pregunta se refiera al proyecto. "
    "No inventes datos del proyecto que no estén "
    "presentes en el contexto. "
    "Las rutas indicadas como documento fuente "
    "identifican la procedencia de la información "
    "y no la ubicación de los componentes descritos. "
    "Si es una pregunta general, puedes utilizar "
    "tus conocimientos generales. "
    "Si la pregunta requiere información actual "
    "que no está disponible, indícalo claramente."
)


@dataclass(frozen=True, slots=True)
class PromptPackage:
    system_prompt: str
    user_prompt: str


class PromptBuilder:
    def __init__(
        self,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
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
        query: str,
        context: ContextBlock,
    ) -> PromptPackage:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "query no puede estar vacía"
            )

        user_prompt = "\n".join(
            [
                "INSTRUCCIONES PARA LA RESPUESTA",
                (
                    "Responde a la petición "
                    "situada al final."
                ),
                (
                    "El contexto puede contener "
                    "información relevante o "
                    "información no relacionada."
                ),
                (
                    "Utiliza solamente las partes "
                    "que ayuden a responder."
                ),
                "",
                "INICIO DEL CONTEXTO",
                context.text,
                "FIN DEL CONTEXTO",
                "",
                "PETICIÓN DEL USUARIO",
                clean_query,
            ]
        )

        return PromptPackage(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
        )