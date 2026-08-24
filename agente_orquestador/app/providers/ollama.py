from __future__ import annotations

import time

import httpx

import re
from app.providers.base import (
    LanguageProviderError,
    LanguageResponse,
)


DEFAULT_SYSTEM_PROMPT = (
    "Eres el Agente Orquestador de José. "
    "Responde siempre en español, de forma "
    "clara, práctica y directa. "
    "Devuelve únicamente la respuesta final. "
    "No muestres razonamientos internos."
)


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 300.0,
    ) -> None:
        clean_url = base_url.strip().rstrip("/")
        clean_model = model.strip()

        if not clean_url:
            raise ValueError(
                "base_url no puede estar vacía"
            )

        if not clean_model:
            raise ValueError(
                "model no puede estar vacío"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser "
                "mayor que cero"
            )

        self._base_url = clean_url
        self._model = clean_model
        self._timeout_seconds = (
            timeout_seconds
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LanguageResponse:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError(
                "prompt no puede estar vacío"
            )

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt
                        or DEFAULT_SYSTEM_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"/no_think\n{clean_prompt}"
                    ),
                },
            ],
            "stream": False,
            "think": False,
            "options": {
                "num_predict": 1200,
                "temperature": 0.2,
            },
        }

        timeout = httpx.Timeout(
            connect=10.0,
            read=self._timeout_seconds,
            write=30.0,
            pool=10.0,
        )

        started_at = time.perf_counter()

        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=timeout,
            )

            response.raise_for_status()

        except httpx.ConnectError as error:
            raise LanguageProviderError(
                "No se puede conectar con "
                f"Ollama en {self._base_url}"
            ) from error

        except httpx.TimeoutException as error:
            raise LanguageProviderError(
                "Ollama ha tardado demasiado "
                "en responder"
            ) from error

        except httpx.HTTPStatusError as error:
            raise LanguageProviderError(
                "Ollama ha devuelto el error "
                f"HTTP {error.response.status_code}"
            ) from error

        elapsed_seconds = (
            time.perf_counter()
            - started_at
        )

        try:
            data = response.json()

            if data.get("done_reason") == "length":
                raise LanguageProviderError(
                    "La respuesta ha superado "
                    "la longitud máxima"
                )

            content = (
                data["message"]["content"]
                .strip()
            )

            content = self._remove_thinking(
                content
            )
        except LanguageProviderError:
            raise

        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            raise LanguageProviderError(
                "La respuesta de Ollama no tiene "
                "el formato esperado"
            ) from error

        if not content:
            raise LanguageProviderError(
                "Ollama ha devuelto una "
                "respuesta vacía"
            )

        return LanguageResponse(
            text=content,
            model=self._model,
            elapsed_seconds=round(
                elapsed_seconds,
                3,
            ),
        )

    @staticmethod
    def _remove_thinking(
        content: str,
    ) -> str:
        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            content,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        ).strip()

        if "</think>" in cleaned.lower():
            closing_position = (
                cleaned.lower()
                .rfind("</think>")
            )

            cleaned = cleaned[
                closing_position
                + len("</think>")
            ].strip()

        return cleaned