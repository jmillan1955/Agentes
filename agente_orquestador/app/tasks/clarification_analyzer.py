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

    _QUESTIONS = {
        "objective": (
            "¿Cuál es el objetivo principal "
            "del proyecto?"
        ),
        "application_type": (
            "¿Qué tipo de aplicación necesitas: "
            "web, móvil, escritorio, Telegram, "
            "consola u otra?"
        ),
        "users": (
            "¿Quiénes utilizarán la aplicación "
            "y qué podrán hacer?"
        ),
        "functionality": (
            "¿Qué funcionalidades principales "
            "debe incluir?"
        ),
        "persistence": (
            "¿Qué información debe guardar "
            "permanentemente?"
        ),
        "runtime": (
            "¿Dónde debe ejecutarse y cómo "
            "quieres acceder a ella?"
        ),
        "technology": (
            "¿Existen restricciones o "
            "preferencias tecnológicas?"
        ),
        "completion": (
            "¿Qué condiciones deben cumplirse "
            "para considerar terminada la "
            "primera versión?"
        ),
    }

    _OBJECTIVE_TERMS = (
        "anade",
        "actualiza",
        "automatiza",
        "construye",
        "crea",
        "corrige",
        "desarrolla",
        "genera",
        "implementa",
        "modifica",
        "organiza",
        "prepara",
        "repara",
    )

    _APPLICATION_TERMS = (
        "api",
        "aplicacion",
        "automatizacion",
        "consola",
        "escritorio",
        "home assistant",
        "movil",
        "script",
        "servicio",
        "telegram",
        "web",
        "windows",
    )

    _TECHNOLOGY_TERMS = (
        ".net",
        "angular",
        "c#",
        "fastapi",
        "flask",
        "home assistant",
        "java",
        "javascript",
        "python",
        "react",
        "sqlite",
        "tkinter",
        "typescript",
        "yaml",
    )

    _RUNTIME_TERMS = (
        "android",
        "docker",
        "home assistant",
        "local",
        "navegador",
        "servidor",
        "telegram",
        "ubuntu",
        "web",
        "windows",
    )

    _COMPLETION_TERMS = (
        "criterios de finalizacion",
        "debe iniciarse",
        "debe abrir",
        "pytest",
        "pruebas",
        "tests",
    )

    _PERSISTENCE_TERMS = (
        "base de datos",
        "guardar",
        "historial",
        "json",
        "persistencia",
        "sqlite",
        "sin guardar",
        "sin persistencia",
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

        return self._analyze_generic(task)

    def _analyze_generic(
        self,
        task: TaskRecord,
    ) -> tuple[str, ...]:
        text = self._normalize(
            " ".join(
                (
                    task.title,
                    task.description,
                )
            )
        )
        questions: list[str] = []

        if not self._contains_any(
            text,
            self._OBJECTIVE_TERMS,
        ):
            questions.append(
                self._QUESTIONS["objective"]
            )

        if not self._contains_any(
            text,
            self._APPLICATION_TERMS,
        ):
            questions.append(
                self._QUESTIONS[
                    "application_type"
                ]
            )

        if (
            self._is_generic_application(text)
            and not self._mentions_users(text)
        ):
            questions.append(
                self._QUESTIONS["users"]
            )

        if not self._has_functional_detail(text):
            questions.append(
                self._QUESTIONS["functionality"]
            )

        if (
            self._needs_persistence_decision(text)
            and not self._contains_any(
                text,
                self._PERSISTENCE_TERMS,
            )
        ):
            questions.append(
                self._QUESTIONS["persistence"]
            )

        if not self._contains_any(
            text,
            self._RUNTIME_TERMS,
        ):
            questions.append(
                self._QUESTIONS["runtime"]
            )

        if not self._contains_any(
            text,
            self._TECHNOLOGY_TERMS,
        ):
            questions.append(
                self._QUESTIONS["technology"]
            )

        if not self._contains_any(
            text,
            self._COMPLETION_TERMS,
        ):
            questions.append(
                self._QUESTIONS["completion"]
            )

        return tuple(questions)

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

    @classmethod
    def _is_generic_application(
        cls,
        text: str,
    ) -> bool:
        technical_types = (
            "api",
            "automatizacion",
            "consola",
            "escritorio",
            "home assistant",
            "script",
            "telegram",
        )
        return (
            "aplicacion" in text
            and not cls._contains_any(
                text,
                technical_types,
            )
        )

    @staticmethod
    def _mentions_users(text: str) -> bool:
        return any(
            term in text
            for term in (
                "administrador",
                "familia",
                "jugador",
                "usuario",
                "utilizaran",
            )
        )

    @staticmethod
    def _has_functional_detail(
        text: str,
    ) -> bool:
        detail_markers = (
            "debe incluir",
            "funcionalidades",
            "permitir",
            "botones",
            "endpoint",
            "cuando ",
            "que ",
        )
        word_count = len(text.split())
        return (
            word_count >= 18
            or any(
                marker in text
                for marker in detail_markers
            )
        )

    @staticmethod
    def _needs_persistence_decision(
        text: str,
    ) -> bool:
        no_persistence_types = (
            "automatizacion",
            "calculadora",
            "corrige",
            "error",
            "home assistant",
            "repara",
            "script",
        )
        return not any(
            term in text
            for term in no_persistence_types
        )

    @staticmethod
    def _contains_any(
        text: str,
        terms: tuple[str, ...],
    ) -> bool:
        return any(
            term in text
            for term in terms
        )

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
