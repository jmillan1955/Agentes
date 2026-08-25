from __future__ import annotations

import re
import unicodedata

from app.routing.models import (
    RequestKind,
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

        if normalized_text.startswith("/"):
            return RoutingDecision(
                kind=RequestKind.COMMAND,
                summary=clean_text,
                confidence=1.0,
            )

        first_word = self._first_word(
            normalized_text
        )

        project_name = self._detect_project(
            original_text=clean_text,
            normalized_text=normalized_text,
        )

        if first_word in self._TASK_VERBS:
            return RoutingDecision(
                kind=RequestKind.TASK,
                summary=clean_text,
                confidence=0.90,
                project_name=project_name,
            )

        if project_name is not None:
            return RoutingDecision(
                kind=RequestKind.PROJECT_QUERY,
                summary=clean_text,
                confidence=0.85,
                project_name=project_name,
            )

        return RoutingDecision(
            kind=RequestKind.GENERAL_QUERY,
            summary=clean_text,
            confidence=0.70,
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