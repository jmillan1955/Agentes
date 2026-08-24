from __future__ import annotations

import httpx
import pytest

from app.providers import (
    LanguageProviderError,
    OllamaProvider,
)


class FakeResponse:
    def __init__(
        self,
        data: dict,
    ) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


def test_generates_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_post(
        url: str,
        json: dict,
        timeout: httpx.Timeout,
    ) -> FakeResponse:
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )

        return FakeResponse(
            {
                "message": {
                    "content": (
                        "Respuesta generada"
                    )
                },
                "done": True,
            }
        )

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
    )

    response = provider.generate(
        prompt="Explica el contexto",
    )

    assert response.text == (
        "Respuesta generada"
    )
    assert response.model == "qwen3:4b"
    assert response.elapsed_seconds >= 0

    assert len(calls) == 1
    assert calls[0]["url"] == (
        "http://127.0.0.1:11434/api/chat"
    )
    assert calls[0]["json"]["stream"] is False
    assert (
        calls[0]["json"]["messages"][1]
        ["content"]
        == "/no_think\nExplica el contexto"
    )


def test_rejects_empty_prompt() -> None:
    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
    )

    with pytest.raises(
        ValueError,
        match="prompt no puede estar vacío",
    ):
        provider.generate("   ")


def test_controls_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str,
        json: dict,
        timeout: httpx.Timeout,
    ) -> FakeResponse:
        request = httpx.Request(
            "POST",
            url,
        )

        raise httpx.ConnectError(
            "Sin conexión",
            request=request,
        )

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
    )

    with pytest.raises(
        LanguageProviderError,
        match="No se puede conectar",
    ):
        provider.generate(
            "Prueba de conexión"
        )


def test_rejects_empty_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str,
        json: dict,
        timeout: httpx.Timeout,
    ) -> FakeResponse:
        return FakeResponse(
            {
                "message": {
                    "content": "   "
                },
                "done": True,
            }
        )

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
    )

    with pytest.raises(
        LanguageProviderError,
        match="respuesta vacía",
    ):
        provider.generate(
            "Genera una respuesta"
        )

def test_removes_internal_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str,
        json: dict,
        timeout: httpx.Timeout,
    ) -> FakeResponse:
        return FakeResponse(
            {
                "message": {
                    "content": (
                        "<think>\n"
                        "Razonamiento interno que "
                        "no debe mostrarse.\n"
                        "</think>\n\n"
                        "Esta es la respuesta final."
                    )
                },
                "done": True,
            }
        )

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
    )

    response = provider.generate(
        "Genera una respuesta"
    )

    assert response.text == (
        "Esta es la respuesta final."
    )
    assert "<think>" not in response.text
    assert "Razonamiento interno" not in (
        response.text
    )