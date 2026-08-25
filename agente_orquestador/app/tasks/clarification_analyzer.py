from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.tasks.models import TaskRecord


@dataclass(frozen=True, slots=True)
class RequirementRule:
    key: str
    question: str
    accepted_terms: tuple[str, ...]


class TaskClarificationAnalyzer:
    _AUDIO_TEXT_RULES = (
        RequirementRule(
            key="input_format",
            question=(
                "¿Qué formatos de entrada debe "
                "admitir: TXT, EPUB, PDF u otros?"
            ),
            accepted_terms=(
                "txt",
                "epub",
                "pdf",
                "docx",
                "markdown",
            ),
        ),
        RequirementRule(
            key="output_format",
            question=(
                "¿Qué formato de salida quieres: "
                "MP3, M4B, WAV u otro?"
            ),
            accepted_terms=(
                "mp3",
                "m4b",
                "wav",
                "ogg",
            ),
        ),
        RequirementRule(
            key="tts_engine",
            question=(
                "¿Qué motor de voz debe utilizar: "
                "Kokoro, Piper u otro?"
            ),
            accepted_terms=(
                "kokoro",
                "piper",
                "espeak",
            ),
        ),
        RequirementRule(
            key="channel",
            question=(
                "¿Qué canal se utilizará para "
                "recibir el texto y entregar "
                "el audio: Telegram, consola "
                "o interfaz web?"
            ),
            accepted_terms=(
                "telegram",
                "consola",
                "web",
            ),
        ),
        RequirementRule(
            key="voice_selection",
            question=(
                "¿La voz será fija o podrá "
                "seleccionarse en cada conversión?"
            ),
            accepted_terms=(
                "voz fija",
                "voz configurable",
                "seleccionar voz",
                "seleccionable",
                "cada conversion",
            ),
        ),
    )

    _GENERIC_PROJECT_QUESTIONS = (
        (
            "¿Cuál es el objetivo principal "
            "del proyecto?"
        ),
        (
            "¿Qué tipo de aplicación necesitas: "
            "web, móvil, escritorio, Telegram, "
            "consola u otra?"
        ),
        (
            "¿Quiénes utilizarán la aplicación "
            "y qué podrán hacer?"
        ),
        (
            "¿Qué funcionalidades principales "
            "debe incluir?"
        ),
        (
            "¿Qué información debe guardar "
            "permanentemente?"
        ),
        (
            "¿Dónde debe ejecutarse y cómo "
            "quieres acceder a ella?"
        ),
        (
            "¿Existen restricciones o "
            "preferencias tecnológicas?"
        ),
        (
            "¿Qué condiciones deben cumplirse "
            "para considerar terminada la "
            "primera versión?"
        ),
    )

    def analyze(
        self,
        task: TaskRecord,
    ) -> tuple[str, ...]:
        project_name = self._normalize(
            task.target_project_name or ""
        )

        if project_name in {
            "agente_audiotext",
            "audiotext",
        }:
            return self._analyze_audio_text(
                task
            )

        return self._GENERIC_PROJECT_QUESTIONS

    def _analyze_audio_text(
        self,
        task: TaskRecord,
    ) -> tuple[str, ...]:
        searchable_text = self._normalize(
            " ".join(
                [
                    task.title,
                    task.description,
                ]
            )
        )

        missing_questions = []

        for rule in self._AUDIO_TEXT_RULES:
            if not any(
                term in searchable_text
                for term in rule.accepted_terms
            ):
                missing_questions.append(
                    rule.question
                )

        return tuple(missing_questions)

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize(
            "NFKD",
            text,
        )

        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        return (
            without_accents
            .lower()
            .strip()
        )