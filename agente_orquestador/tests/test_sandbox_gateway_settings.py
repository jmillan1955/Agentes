from pathlib import Path

import pytest

from sandbox_gateway.settings import (
    GatewaySettings,
)


def configure_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SANDBOX_GATEWAY_TOKEN",
        "a" * 32,
    )


def test_loads_gateway_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_token(monkeypatch)

    settings = GatewaySettings.load()

    assert (
        settings.docker_image
        == "orchestrator-pytest:3.12"
    )
    assert settings.port == 8091
    assert settings.limits.max_files == 200


def test_loads_custom_temporary_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_token(monkeypatch)
    monkeypatch.setenv(
        "SANDBOX_TEMPORARY_ROOT",
        str(tmp_path),
    )

    settings = GatewaySettings.load()

    assert (
        settings.temporary_root
        == tmp_path.resolve()
    )


def test_rejects_short_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SANDBOX_GATEWAY_TOKEN",
        "corto",
    )

    with pytest.raises(
        RuntimeError,
        match="al menos 32",
    ):
        GatewaySettings.load()


def test_rejects_relative_temporary_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_token(monkeypatch)
    monkeypatch.setenv(
        "SANDBOX_TEMPORARY_ROOT",
        "ruta/relativa",
    )

    with pytest.raises(
        RuntimeError,
        match="debe ser absoluta",
    ):
        GatewaySettings.load()