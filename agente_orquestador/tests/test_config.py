from __future__ import annotations

import pytest

from config import Settings


def configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN",
        "token-de-prueba",
    )
    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_ID",
        "123456",
    )
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://192.168.1.131:11434",
    )
    monkeypatch.setenv(
        "OLLAMA_MODEL",
        "qwen3:4b",
    )
    monkeypatch.setenv(
        "OLLAMA_TIMEOUT_SECONDS",
        "300",
    )


def test_loads_ollama_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    settings = Settings.load()

    assert settings.ollama_base_url == (
        "http://192.168.1.131:11434"
    )
    assert settings.ollama_model == "qwen3:4b"
    assert (
        settings.ollama_timeout_seconds
        == 300.0
    )


def test_rejects_empty_ollama_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "   ",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "OLLAMA_BASE_URL no puede "
            "estar vacía"
        ),
    ):
        Settings.load()


def test_rejects_invalid_ollama_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )
    monkeypatch.setenv(
        "OLLAMA_TIMEOUT_SECONDS",
        "mucho",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "OLLAMA_TIMEOUT_SECONDS debe "
            "ser un número"
        ),
    ):
        Settings.load()