from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LanguageProviderError(Exception):
    """Error al utilizar un proveedor de lenguaje."""


@dataclass(frozen=True, slots=True)
class LanguageResponse:
    text: str
    model: str
    elapsed_seconds: float


class LanguageProvider(Protocol):
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LanguageResponse:
        """Genera una respuesta de lenguaje."""