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
    provider: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


class LanguageProvider(Protocol):
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: str | None = None,
    ) -> LanguageResponse:
        """Genera una respuesta de lenguaje."""
