from __future__ import annotations

import re


class VerificationPolicy:
    """Decide cuándo una consulta general necesita fuentes web."""

    _CURRENT_PATTERNS = (
        r"\bhoy\b",
        r"\bahora\b",
        r"\bactual(?:es|mente)?\b",
        r"\búltim[oa]s?\b",
        r"\breciente(?:s)?\b",
        r"\bnoticias?\b",
        r"\bprecio(?:s)?\b",
        r"\bcoste(?:s)?\b",
        r"\bcotización\b",
        r"\bhorario(?:s)?\b",
        r"\bversión(?:es)?\b",
        r"\bdocumentación\b",
        r"\bapi\b",
        r"\bley(?:es)?\b",
        r"\bnormativa\b",
        r"\bpresidente\b",
        r"\bceo\b",
        r"\bresultado(?:s)?\b",
        r"\bclasificación\b",
        r"\btiempo\b",
        r"\bprevisión\b",
        r"\bsegún\b.+\bfuente",
        r"\bcomprueba\b",
        r"\bverifica\b",
        r"\bbusca\b",
        r"\benlace(?:s)?\b",
    )

    def __init__(self, mode: str = "automatic") -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"automatic", "on_demand"}:
            raise ValueError("Modo de verificación no válido")
        self._mode = normalized_mode
        self._pattern = re.compile(
            "|".join(self._CURRENT_PATTERNS),
            flags=re.IGNORECASE,
        )

    def requires_web(self, query: str) -> bool:
        if self._mode != "automatic":
            return False
        return bool(self._pattern.search(query.strip()))
