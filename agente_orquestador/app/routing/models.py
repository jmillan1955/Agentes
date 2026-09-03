from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RequestKind(str, Enum):
    GENERAL_QUERY = "general_query"
    PROJECT_QUERY = "project_query"
    TASK = "task"
    CLARIFICATION = "clarification"
    COMMAND = "command"


class RequestSubtype(str, Enum):
    UNKNOWN = "unknown"
    COMMAND = "command"
    SOCIAL = "social"
    GENERAL_RESPONSE = "general_response"
    PROVIDER_RESPONSE = "provider_response"
    PROVIDER_COMPARISON = "provider_comparison"
    CURRENT_INFORMATION = "current_information"
    PROJECT_INFORMATION = "project_information"
    PROJECT_TASK = "project_task"
    PYTHON_SCRIPT = "python_script"
    DESKTOP_PYTHON_APP = "desktop_python_app"
    HOME_ASSISTANT_YAML = "home_assistant_yaml"
    BACKEND_API = "backend_api"
    BUG_FIX = "bug_fix"


class ProviderPreference(str, Enum):
    DEFAULT = "default"
    INTERNAL = "internal"
    OLLAMA = "ollama"
    OPENAI = "openai"
    CODEX = "codex"
    COMPARISON = "comparison"
    VERIFICATION = "verification"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    kind: RequestKind
    summary: str
    confidence: float
    project_name: str | None = None
    missing_information: tuple[str, ...] = field(
        default_factory=tuple
    )
    subtype: RequestSubtype = RequestSubtype.UNKNOWN
    provider: ProviderPreference = ProviderPreference.DEFAULT

    def __post_init__(self) -> None:
        clean_summary = self.summary.strip()

        if not clean_summary:
            raise ValueError(
                "summary no puede estar vacío"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence debe estar "
                "entre 0 y 1"
            )

        clean_project_name = (
            self.project_name.strip()
            if self.project_name is not None
            else None
        )

        clean_missing_information = tuple(
            value.strip()
            for value in self.missing_information
            if value.strip()
        )

        object.__setattr__(
            self,
            "summary",
            clean_summary,
        )
        object.__setattr__(
            self,
            "project_name",
            clean_project_name or None,
        )
        object.__setattr__(
            self,
            "missing_information",
            clean_missing_information,
        )

    @property
    def requires_clarification(self) -> bool:
        return (
            self.kind == RequestKind.CLARIFICATION
            or bool(self.missing_information)
        )
