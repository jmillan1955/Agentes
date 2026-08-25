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
        "OLLAMA_GENERAL_MODEL",
        "llama3.2:3b",
    )
    monkeypatch.setenv(
        "OLLAMA_CODING_MODEL",
        "qwen2.5-coder:3b",
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
    assert (
        settings.ollama_general_model
        == "llama3.2:3b"
    )
    assert (
        settings.ollama_coding_model
        == "qwen2.5-coder:3b"
    )
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
            "estar vacÃ­a"
        ),
    ):
        Settings.load()


def test_rejects_empty_general_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )
    monkeypatch.setenv(
        "OLLAMA_GENERAL_MODEL",
        "   ",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "OLLAMA_GENERAL_MODEL no puede "
            "estar vacÃ­o"
        ),
    ):
        Settings.load()


def test_rejects_empty_coding_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )
    monkeypatch.setenv(
        "OLLAMA_CODING_MODEL",
        "   ",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "OLLAMA_CODING_MODEL no puede "
            "estar vacÃ­o"
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
            "ser un nÃºmero"
        ),
    ):
        Settings.load()

def test_loads_multiple_telegram_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456,234567,345678,456789",
    )

    settings = Settings.load()

    assert (
        settings.telegram_allowed_user_ids
        == (
            123456,
            234567,
            345678,
            456789,
        )
    )


def test_rejects_invalid_telegram_user_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456,usuario-invalido",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_ALLOWED_USER_IDS debe "
            "contener numeros enteros"
        ),
    ):
        Settings.load()