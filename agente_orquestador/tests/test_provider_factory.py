from __future__ import annotations

import pytest

import main as main_module
from config import Settings

from test_config import configure_required_environment


def test_creates_openai_coding_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAIProvider:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    configure_required_environment(monkeypatch)
    monkeypatch.setenv("CODING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "key-de-prueba")
    monkeypatch.setenv("OPENAI_CODING_MODEL", "gpt-5-mini")
    monkeypatch.setenv("OPENAI_CODING_TIMEOUT_SECONDS", "240")
    monkeypatch.setattr(
        main_module, "OpenAIProvider", FakeOpenAIProvider
    )
    settings = Settings.load()

    provider = main_module.create_language_provider(
        settings,
        settings.coding_provider,
        coding=True,
    )

    assert isinstance(provider, FakeOpenAIProvider)
    assert captured["model"] == "gpt-5-mini"
    assert captured["timeout_seconds"] == 240.0
    assert captured["reasoning_effort"] == "low"
    assert captured["input_cost_per_million"] == 0.25
    assert captured["output_cost_per_million"] == 2.0


def test_creates_ollama_coding_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeOllamaProvider:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    configure_required_environment(monkeypatch)
    monkeypatch.setenv("CODING_PROVIDER", "ollama")
    monkeypatch.setattr(
        main_module, "OllamaProvider", FakeOllamaProvider
    )
    settings = Settings.load()

    provider = main_module.create_language_provider(
        settings,
        settings.coding_provider,
        coding=True,
    )

    assert isinstance(provider, FakeOllamaProvider)
    assert captured["model"] == "qwen2.5-coder:3b"
    assert captured["timeout_seconds"] == 900.0


def test_rejects_combined_planning_and_coding_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(monkeypatch)
    settings = Settings.load()

    with pytest.raises(ValueError, match="planificacion y codigo"):
        main_module.create_language_provider(
            settings,
            "ollama",
            planning=True,
            coding=True,
        )
