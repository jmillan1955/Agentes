from __future__ import annotations

import time
import httpx

from app.providers.base import LanguageProviderError, LanguageResponse


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite",
                 timeout_seconds: float = 120.0) -> None:
        if not api_key.strip() or not model.strip() or timeout_seconds <= 0:
            raise ValueError("Configuracion Gemini no valida")
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._timeout = timeout_seconds

    def generate(self, prompt: str, system_prompt: str | None = None,
                 response_format: str | None = None) -> LanguageResponse:
        if not prompt.strip():
            raise ValueError("prompt no puede estar vacio")
        if response_format not in (None, "json"):
            raise ValueError("response_format solamente admite json")
        config = {"temperature": 0.2}
        if response_format == "json":
            config["responseMimeType"] = "application/json"
        payload = {
            "contents": [{"parts": [{"text": prompt.strip()}]}],
            "generationConfig": config,
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        started = time.perf_counter()
        try:
            response = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self._model}:generateContent",
                headers={"x-goog-api-key": self._api_key}, json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as error:
            raise LanguageProviderError(f"Gemini no ha podido responder: {error}") from error
        if not content:
            raise LanguageProviderError("Gemini ha devuelto una respuesta vacia")
        usage = data.get("usageMetadata", {})
        return LanguageResponse(
            text=content, model=self._model,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            provider="gemini", input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"), estimated_cost_usd=0.0,
        )
