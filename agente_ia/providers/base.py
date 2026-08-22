from __future__ import annotations

from typing import Protocol


class ProviderError(Exception):
    """Error producido al utilizar un proveedor de IA."""


class LanguageProvider(Protocol):
    def responder(self, texto: str) -> str:
        """Genera una respuesta a partir de un texto."""