import base64

import pytest

from sandbox_gateway.models import (
    GatewayLimits,
    PytestJobRequest,
    SandboxFilePayload,
)


def encode(value: bytes) -> str:
    return base64.b64encode(
        value
    ).decode("ascii")


def create_file(
    path: str = "tests/test_example.py",
    content: bytes = b"def test_ok(): pass\n",
) -> SandboxFilePayload:
    return SandboxFilePayload(
        relative_path=path,
        content_base64=encode(content),
    )


def test_validates_safe_job() -> None:
    request = PytestJobRequest(
        files=(create_file(),),
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )

    request.validate(
        GatewayLimits()
    )


@pytest.mark.parametrize(
    "path",
    (
        "../fuera.py",
        "/ruta/absoluta.py",
        "C:\\ruta\\absoluta.py",
        "\\\\servidor\\archivo.py",
    ),
)
def test_rejects_unsafe_file_path(
    path: str,
) -> None:
    with pytest.raises(ValueError):
        create_file(path=path)


def test_rejects_invalid_base64() -> None:
    with pytest.raises(
        ValueError,
        match="no es valido",
    ):
        SandboxFilePayload(
            relative_path="test.py",
            content_base64="***",
        )


def test_rejects_duplicate_paths() -> None:
    request = PytestJobRequest(
        files=(
            create_file(),
            create_file(),
        ),
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )

    with pytest.raises(
        ValueError,
        match="duplicadas",
    ):
        request.validate(
            GatewayLimits()
        )


def test_rejects_total_size_limit() -> None:
    request = PytestJobRequest(
        files=(
            create_file(
                content=b"12345"
            ),
        ),
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )

    with pytest.raises(
        ValueError,
        match="tamano maximo",
    ):
        request.validate(
            GatewayLimits(
                max_total_bytes=4
            )
        )


def test_rejects_timeout_over_limit() -> None:
    request = PytestJobRequest(
        files=(create_file(),),
        test_target="tests",
        timeout_seconds=121.0,
        max_output_characters=20_000,
    )

    with pytest.raises(
        ValueError,
        match="timeout_seconds",
    ):
        request.validate(
            GatewayLimits()
        )