from types import SimpleNamespace

import httpx
import pytest

import app.providers.openai as openai_module
from app.providers import GeminiProvider, OpenAIProvider, ProviderComparisonService


def test_openai_reports_usage_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    request = {}
    class FakeResponses:
        def create(self, **kwargs):
            request.update(kwargs)
            return SimpleNamespace(
                output_text="Respuesta OpenAI",
                usage=SimpleNamespace(input_tokens=100, output_tokens=20),
            )
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()
    monkeypatch.setattr(openai_module, "OpenAI", FakeOpenAI)
    result = OpenAIProvider(
        "key", "gpt-5", input_cost_per_million=1.25,
        output_cost_per_million=10,
    ).generate("Pregunta")
    assert result.provider == "openai"
    assert result.estimated_cost_usd == 0.000325
    assert request["reasoning"] == {"effort": "minimal"}


def test_gemini_reports_free_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "Gemini"}]}}],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 3},
            }
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse())
    result = GeminiProvider("key").generate("Pregunta")
    assert result.provider == "gemini"
    assert result.estimated_cost_usd == 0.0


def test_comparison_includes_all_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        def __init__(self, name): self.name = name
        def generate(self, *args, **kwargs):
            from app.providers import LanguageResponse
            return LanguageResponse(self.name, self.name, 1.0, provider=self.name)
    text, models = ProviderComparisonService({
        "openai": FakeProvider("openai"),
        "gemini": FakeProvider("gemini"),
        "ollama": FakeProvider("ollama"),
    }).compare("Pregunta")
    assert all(name.upper() in text for name in ("openai", "gemini", "ollama"))
    assert models == ("openai", "gemini", "ollama")



def test_openai_web_search_is_required_and_sources_are_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {}

    class Citation:
        type = "url_citation"
        url = "https://example.com/documentacion"
        title = "Documentación oficial"

    class FakeResponses:
        def create(self, **kwargs):
            request.update(kwargs)
            return SimpleNamespace(
                output_text="Respuesta verificada",
                output=[
                    SimpleNamespace(
                        content=[
                            SimpleNamespace(
                                annotations=[Citation()]
                            )
                        ]
                    )
                ],
                usage=SimpleNamespace(
                    input_tokens=12,
                    output_tokens=8,
                ),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr(
        openai_module,
        "OpenAI",
        FakeOpenAI,
    )
    result = OpenAIProvider(
        "key",
        "gpt-5",
        reasoning_effort="low",
        web_search_enabled=True,
    ).generate("Consulta actual")

    assert request["tools"] == [
        {
            "type": "web_search",
            "search_context_size": "low",
        }
    ]
    assert request["tool_choice"] == "required"
    assert request["reasoning"] == {
        "effort": "low"
    }
    assert "https://example.com/documentacion" in result.text
