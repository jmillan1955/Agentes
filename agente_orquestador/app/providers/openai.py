from __future__ import annotations

import time
from openai import OpenAI

from app.providers.base import LanguageProviderError, LanguageResponse


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 120.0,
                 input_cost_per_million: float = 0.0,
                 output_cost_per_million: float = 0.0) -> None:
        if not api_key.strip() or not model.strip() or timeout_seconds <= 0:
            raise ValueError("Configuracion OpenAI no valida")
        self._model = model.strip()
        self._client = OpenAI(api_key=api_key.strip(), timeout=timeout_seconds)
        self._input_cost = input_cost_per_million
        self._output_cost = output_cost_per_million

    def generate(self, prompt: str, system_prompt: str | None = None,
                 response_format: str | None = None) -> LanguageResponse:
        if not prompt.strip():
            raise ValueError("prompt no puede estar vacio")
        if response_format not in (None, "json"):
            raise ValueError("response_format solamente admite json")
        started = time.perf_counter()
        try:
            response = self._client.responses.create(
                model=self._model, instructions=system_prompt,
                input=prompt.strip(),
                text=({"format": {"type": "json_object"}}
                      if response_format == "json" else None),
            )
        except Exception as error:
            raise LanguageProviderError(f"OpenAI no ha podido responder: {error}") from error
        content = (response.output_text or "").strip()
        if not content:
            raise LanguageProviderError("OpenAI ha devuelto una respuesta vacia")
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        cost = None
        if input_tokens is not None and output_tokens is not None:
            cost = round((input_tokens * self._input_cost
                          + output_tokens * self._output_cost) / 1_000_000, 8)
        return LanguageResponse(
            text=content, model=self._model,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            provider="openai", input_tokens=input_tokens,
            output_tokens=output_tokens, estimated_cost_usd=cost,
        )
