from __future__ import annotations

import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai import OpenAI

from app.providers.base import LanguageProviderError, LanguageResponse


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 120.0,
                 input_cost_per_million: float = 0.0,
                 output_cost_per_million: float = 0.0,
                 reasoning_effort: str = "minimal",
                 web_search_enabled: bool = False,
                 web_search_context_size: str = "low") -> None:
        if not api_key.strip() or not model.strip() or timeout_seconds <= 0:
            raise ValueError("Configuracion OpenAI no valida")
        self._model = model.strip()
        self._client = OpenAI(api_key=api_key.strip(), timeout=timeout_seconds)
        self._input_cost = input_cost_per_million
        self._output_cost = output_cost_per_million
        supported_efforts = {"minimal", "low", "medium", "high"}
        if reasoning_effort not in supported_efforts:
            raise ValueError("Esfuerzo de razonamiento OpenAI no valido")
        self._reasoning_effort = reasoning_effort
        self._web_search_enabled = web_search_enabled
        if web_search_context_size not in {
            "low", "medium", "high"
        }:
            raise ValueError(
                "Tamaño de contexto web no válido"
            )
        self._web_search_context_size = (
            web_search_context_size
        )

    def generate(self, prompt: str, system_prompt: str | None = None,
                 response_format: str | None = None) -> LanguageResponse:
        if not prompt.strip():
            raise ValueError("prompt no puede estar vacio")
        if response_format not in (None, "json"):
            raise ValueError("response_format solamente admite json")
        clean_prompt = prompt.strip()
        instructions = system_prompt
        if response_format == "json":
            json_instruction = (
                "Devuelve exclusivamente un objeto JSON valido."
            )
            instructions = (
                f"{system_prompt}\n\n{json_instruction}"
                if system_prompt
                else json_instruction
            )
            clean_prompt = (
                f"{clean_prompt}\n\n{json_instruction}"
            )
        started = time.perf_counter()
        try:
            request = {
                "model": self._model,
                "instructions": instructions,
                "input": clean_prompt,
                "reasoning": {
                    "effort": self._reasoning_effort
                },
                "text": (
                    {"format": {"type": "json_object"}}
                    if response_format == "json"
                    else None
                ),
            }
            if self._web_search_enabled:
                request["tools"] = [
                    {
                        "type": "web_search",
                        "search_context_size": (
                            self
                            ._web_search_context_size
                        ),
                    }
                ]
                request["tool_choice"] = "required"
            response = self._client.responses.create(
                **request
            )
        except Exception as error:
            raise LanguageProviderError(f"OpenAI no ha podido responder: {error}") from error
        content = (response.output_text or "").strip()
        if not content:
            raise LanguageProviderError("OpenAI ha devuelto una respuesta vacia")
        if self._web_search_enabled:
            content = self._strip_inline_citations(
                content,
                response,
            )
            sources = self._extract_web_sources(
                response
            )
            if sources:
                source_lines = [
                    "",
                    "FUENTES",
                    *(
                        f"- {title}: {url}"
                        for title, url in sources
                    ),
                ]
                content = "\n".join(
                    [content, *source_lines]
                )
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


    @staticmethod
    def _extract_web_sources(response) -> tuple[tuple[str, str], ...]:
        sources: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                for annotation in (
                    getattr(content, "annotations", ())
                    or ()
                ):
                    if getattr(annotation, "type", "") != "url_citation":
                        continue
                    citation = getattr(
                        annotation,
                        "url_citation",
                        annotation,
                    )
                    url = OpenAIProvider._clean_source_url(
                        getattr(citation, "url", "")
                    )
                    if not url or url in seen_urls:
                        continue
                    title = (
                        getattr(citation, "title", "")
                        or "Fuente"
                    )
                    seen_urls.add(url)
                    sources.append((title, url))
        return tuple(sources)


    @staticmethod
    def _strip_inline_citations(
        text: str,
        response,
    ) -> str:
        ranges: list[tuple[int, int]] = []
        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                for annotation in (
                    getattr(content, "annotations", ())
                    or ()
                ):
                    if getattr(annotation, "type", "") != "url_citation":
                        continue
                    citation = getattr(
                        annotation,
                        "url_citation",
                        annotation,
                    )
                    start = getattr(
                        citation,
                        "start_index",
                        getattr(
                            annotation,
                            "start_index",
                            None,
                        ),
                    )
                    end = getattr(
                        citation,
                        "end_index",
                        getattr(
                            annotation,
                            "end_index",
                            None,
                        ),
                    )
                    if (
                        isinstance(start, int)
                        and isinstance(end, int)
                        and 0 <= start < end <= len(text)
                    ):
                        ranges.append((start, end))

        cleaned = text
        for start, end in sorted(
            set(ranges),
            reverse=True,
        ):
            cleaned = (
                cleaned[:start].rstrip()
                + cleaned[end:]
            )

        cleaned = re.sub(
            r"\s*\(\[[^\]]+\]\(https?://[^)]+\)\)",
            "",
            cleaned,
        )
        return cleaned.strip()

    @staticmethod
    def _clean_source_url(url: str) -> str:
        if not url:
            return ""
        parts = urlsplit(url)
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if key.lower() != "utm_source"
            ],
            doseq=True,
        )
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                query,
                parts.fragment,
            )
        )
