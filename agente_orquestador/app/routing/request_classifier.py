from __future__ import annotations

import re
import unicodedata

from app.routing.models import (
    ProviderPreference,
    RequestKind,
    RequestSubtype,
    RoutingDecision,
)


class RequestClassifier:
    _TASK_VERBS = {
        "anade",
        "actualiza",
        "borra",
        "cambia",
        "construye",
        "crea",
        "corrige",
        "desarrolla",
        "elimina",
        "genera",
        "implementa",
        "instala",
        "modifica",
        "prepara",
        "publica",
        "repara",
        "revisa",
    }

    _ORCHESTRATOR_TERMS = {
        "agente orquestador",
        "contexto sqlite",
        "context.db",
        "hito",
        "repositorio",
    }

    _GENERIC_PROJECT_WORDS = {
        "el",
        "la",
        "su",
        "un",
        "una",
        "nuevo",
        "nueva",
    }

    _SOCIAL_MESSAGES = {
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "gracias",
        "hola",
        "muchas gracias",
    }

    def classify(
        self,
        text: str,
    ) -> RoutingDecision:
        clean_text = text.strip()

        if not clean_text:
            raise ValueError(
                "text no puede estar vacío"
            )

        normalized_text = self._normalize(
            clean_text
        )
        provider = self._detect_provider(
            normalized_text
        )

        if normalized_text.startswith("/"):
            return RoutingDecision(
                kind=RequestKind.COMMAND,
                summary=clean_text,
                confidence=1.0,
                subtype=RequestSubtype.COMMAND,
                provider=(
                    provider
                    if provider
                    != ProviderPreference.DEFAULT
                    else ProviderPreference.INTERNAL
                ),
            )

        if normalized_text in self._SOCIAL_MESSAGES:
            return RoutingDecision(
                kind=RequestKind.GENERAL_QUERY,
                summary=clean_text,
                confidence=0.98,
                subtype=RequestSubtype.SOCIAL,
                provider=provider,
            )

        first_word = self._first_word(
            normalized_text
        )

        project_name = self._detect_project(
            original_text=clean_text,
            normalized_text=normalized_text,
        )

        project_task_verb = (
            self._project_task_verb(
                normalized_text
            )
        )

        if (
            first_word in self._TASK_VERBS
            or project_task_verb is not None
        ):
            return RoutingDecision(
                kind=RequestKind.TASK,
                summary=clean_text,
                confidence=0.90,
                project_name=project_name,
                subtype=self._detect_task_subtype(
                    normalized_text
                ),
                provider=provider,
            )

        if self._is_comparison(
            normalized_text
        ):
            return RoutingDecision(
                kind=RequestKind.GENERAL_QUERY,
                summary=clean_text,
                confidence=0.95,
                subtype=(
                    RequestSubtype
                    .PROVIDER_COMPARISON
                ),
                provider=(
                    ProviderPreference.COMPARISON
                ),
            )

        if project_name is not None:
            return RoutingDecision(
                kind=RequestKind.PROJECT_QUERY,
                summary=clean_text,
                confidence=0.85,
                project_name=project_name,
                subtype=(
                    RequestSubtype
                    .PROJECT_INFORMATION
                ),
                provider=provider,
            )

        subtype = (
            RequestSubtype.PROVIDER_RESPONSE
            if provider
            in {
                ProviderPreference.OLLAMA,
                ProviderPreference.OPENAI,
                ProviderPreference.CODEX,
            }
            else RequestSubtype.GENERAL_RESPONSE
        )

        if self._needs_current_information(
            normalized_text
        ):
            subtype = (
                RequestSubtype.CURRENT_INFORMATION
            )
            provider = (
                ProviderPreference.VERIFICATION
            )

        return RoutingDecision(
            kind=RequestKind.GENERAL_QUERY,
            summary=clean_text,
            confidence=0.70,
            subtype=subtype,
            provider=provider,
        )

    def _detect_task_subtype(
        self,
        text: str,
    ) -> RequestSubtype:
        if any(
            term in text
            for term in (
                "error",
                "fallo",
                "traceback",
                "pytest",
                "corrige",
                "repara",
            )
        ):
            return RequestSubtype.BUG_FIX

        if (
            "home assistant" in text
            and any(
                term in text
                for term in (
                    "automatizacion",
                    "script",
                    "yaml",
                )
            )
        ):
            return (
                RequestSubtype
                .HOME_ASSISTANT_YAML
            )

        if any(
            term in text
            for term in (
                "fastapi",
                "api rest",
                "backend",
                "endpoint",
            )
        ):
            return RequestSubtype.BACKEND_API

        if (
            "python" in text
            and any(
                term in text
                for term in (
                    "escritorio",
                    "tkinter",
                    "windows",
                )
            )
        ):
            return (
                RequestSubtype
                .DESKTOP_PYTHON_APP
            )

        if (
            "python" in text
            and "script" in text
        ):
            return RequestSubtype.PYTHON_SCRIPT

        return RequestSubtype.PROJECT_TASK

    @staticmethod
    def _detect_provider(
        text: str,
    ) -> ProviderPreference:
        if "codex" in text:
            return ProviderPreference.CODEX
        if "openai" in text:
            return ProviderPreference.OPENAI
        if "ollama" in text:
            return ProviderPreference.OLLAMA
        return ProviderPreference.DEFAULT

    @staticmethod
    def _is_comparison(text: str) -> bool:
        provider_count = sum(
            provider in text
            for provider in (
                "codex",
                "openai",
                "ollama",
                "gemini",
            )
        )
        return (
            provider_count >= 2
            and any(
                term in text
                for term in (
                    "compara",
                    "comparacion",
                    "diferencia",
                )
            )
        )

    @staticmethod
    def _needs_current_information(
        text: str,
    ) -> bool:
        return any(
            term in text
            for term in (
                "actualmente",
                "ultima version",
                "version actual",
                "version estable",
                "hoy",
                "noticias",
                "precio actual",
            )
        )

    def _project_task_verb(
        self,
        normalized_text: str,
    ) -> str | None:
        verbs = "|".join(
            sorted(self._TASK_VERBS)
        )
        match = re.search(
            (
                r"\bproyecto\s+"
                r"[a-z0-9_-]+"
                r"(?:\s*[,;:]\s*|\s+)"
                rf"({verbs})\b"
            ),
            normalized_text,
        )
        return (
            match.group(1)
            if match is not None
            else None
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

        return without_accents.lower().strip()

    @staticmethod
    def _first_word(text: str) -> str:
        match = re.search(
            r"[a-z0-9_]+",
            text,
        )

        if match is None:
            return ""

        return match.group(0)

    def _detect_project(
        self,
        original_text: str,
        normalized_text: str,
    ) -> str | None:
        if (
            "agente orquestador"
            in normalized_text
        ):
            return "Agente Orquestador"

        project_match = re.search(
            (
                r"\bproyecto"
                r"(?:\s+(?:llamado|denominado))?"
                r"\s+"
                r"([A-Za-zÁÉÍÓÚÜÑ"
                r"áéíóúüñ0-9_-]+)"
            ),
            original_text,
            flags=re.IGNORECASE,
        )

        if project_match is not None:
            candidate = (
                project_match.group(1).strip()
            )

            normalized_candidate = (
                self._normalize(candidate)
            )

            if (
                normalized_candidate
                not in self._GENERIC_PROJECT_WORDS
            ):
                return candidate

        if any(
            term in normalized_text
            for term in self._ORCHESTRATOR_TERMS
        ):
            return "Agente Orquestador"

        if "proyecto" in normalized_text:
            return "Agente Orquestador"

        return None
