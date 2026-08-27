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
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456",
    )
    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
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
            "estar vacia"
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
            "estar vacio"
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
            "estar vacio"
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
            "ser un numero"
        ),
    ):
        Settings.load()
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

def test_loads_telegram_approver_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456,234567,345678",
    )
    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
        "123456,234567",
    )

    settings = Settings.load()

    assert (
        settings.telegram_approver_user_ids
        == (
            123456,
            234567,
        )
    )


def test_removes_duplicate_approver_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456,234567",
    )
    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
        "123456,123456",
    )

    settings = Settings.load()

    assert (
        settings.telegram_approver_user_ids
        == (123456,)
    )


def test_rejects_empty_approver_user_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
        "   ",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Falta TELEGRAM_APPROVER_USER_IDS "
            "en .env"
        ),
    ):
        Settings.load()


def test_rejects_invalid_approver_user_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
        "123456,usuario-invalido",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_APPROVER_USER_IDS debe "
            "contener numeros enteros"
        ),
    ):
        Settings.load()


def test_rejects_approver_that_is_not_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_required_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123456,234567",
    )
    monkeypatch.setenv(
        "TELEGRAM_APPROVER_USER_IDS",
        "345678",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Todos los aprobadores deben ser "
            "usuarios autorizados"
        ),
    ):
        Settings.load()