from pathlib import Path

import pytest

from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)


def test_creates_sandbox_request(
    tmp_path: Path,
) -> None:
    request = SandboxRunRequest(
        workspace_path=tmp_path,
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )

    assert (
        request.workspace_path
        == tmp_path.resolve()
    )
    assert request.test_target == "tests"


@pytest.mark.parametrize(
    "test_target",
    (
        "",
        "   ",
        "../fuera",
        "tests/../../fuera",
        "/ruta/absoluta",
        "C:\\ruta\\absoluta",
        "\\\\servidor\\recurso",
    ),
)
def test_rejects_unsafe_test_target(
    tmp_path: Path,
    test_target: str,
) -> None:
    with pytest.raises(ValueError):
        SandboxRunRequest(
            workspace_path=tmp_path,
            test_target=test_target,
            timeout_seconds=60.0,
            max_output_characters=20_000,
        )


def test_rejects_invalid_sandbox_limits(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        SandboxRunRequest(
            workspace_path=tmp_path,
            test_target="tests",
            timeout_seconds=0,
            max_output_characters=20_000,
        )


def test_creates_timeout_result() -> None:
    result = SandboxRunResult(
        exit_code=None,
        stdout_text="",
        stderr_text="Tiempo agotado",
        timed_out=True,
        duration_seconds=60.0,
    )

    assert result.timed_out is True
    assert result.exit_code is None