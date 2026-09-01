from __future__ import annotations

from app.providers.base import LanguageProvider, LanguageProviderError


class ProviderComparisonService:
    def __init__(self, providers: dict[str, LanguageProvider]) -> None:
        if not providers:
            raise ValueError("Debe existir al menos un proveedor")
        self._providers = dict(providers)

    def compare(self, query: str) -> tuple[str, tuple[str, ...]]:
        if not query.strip():
            raise ValueError("La pregunta no puede estar vacia")
        blocks = ["COMPARACION DE MODELOS"]
        models = []
        for name, provider in self._providers.items():
            blocks.extend(["", f"--- {name.upper()} ---"])
            try:
                result = provider.generate(
                    query,
                    "Responde en espanol con precision. No inventes datos.",
                )
                models.append(result.model)
                cost = ("no disponible" if result.estimated_cost_usd is None
                        else f"${result.estimated_cost_usd:.6f}")
                blocks.extend([
                    result.text, "",
                    f"Modelo: {result.model} | Tiempo: {result.elapsed_seconds:.2f} s | "
                    f"Tokens: {result.input_tokens or '-'}+{result.output_tokens or '-'} | "
                    f"Coste estimado: {cost}",
                ])
            except LanguageProviderError as error:
                blocks.append(f"ERROR: {error}")
        return "\n".join(blocks), tuple(models)
