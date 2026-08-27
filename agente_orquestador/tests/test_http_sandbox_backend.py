import json
from pathlib import Path

import httpx
import pytest

from app.execution.http_sandbox_backend import (
    HttpSandboxBackend,
    SandboxGatewayError,
)
from app.execution.sandbox import (
    SandboxRunRequest,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)


def create_workspace(
    tmp_path: Path,
) -> Path:
    workspace = tmp_path / "workspace"
    tests = workspace / "tests"
    tests.mkdir(parents=True)

    (tests / "test_ok.py").write_text(
        "def test_ok(): pass\n",
        encoding="utf-8",
        newline="",
    )
    (workspace / ".env").write_text(
        "SECRETO=no_enviar",
        encoding="utf-8",
    )

    return workspace


def create_request(
    workspace: Path,
) -> SandboxRunRequest:
    return SandboxRunRequest(
        workspace_path=workspace,
        test_target="tests",
        timeout_seconds=30,
        max_output_characters=20_000,
    )


def test_sends_authorized_safe_package(
    tmp_path: Path,
) -> None:
    captured = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured["authorization"] = (
            request.headers[
                "Authorization"
            ]
        )
        captured["payload"] = json.loads(
            request.content
        )

        return httpx.Response(
            200,
            json={
                "exit_code": 0,
                "stdout_text": "1 passed",
                "stderr_text": "",
                "timed_out": False,
                "duration_seconds": 0.5,
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )

    backend = HttpSandboxBackend(
        gateway_url=(
            "http://192.168.1.102:8091"
        ),
        auth_token="a" * 32,
        packager=WorkspacePackager(),
        client=client,
    )

    result = backend.run_pytest(
        create_request(
            create_workspace(tmp_path)
        )
    )

    assert result.exit_code == 0
    assert result.stdout_text == "1 passed"
    assert (
        captured["authorization"]
        == f"Bearer {'a' * 32}"
    )

    paths = [
        file["relative_path"]
        for file in (
            captured["payload"]["files"]
        )
    ]

    assert paths == [
        "tests/test_ok.py"
    ]


def test_rejects_gateway_http_error(
    tmp_path: Path,
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401
            )
        )
    )

    backend = HttpSandboxBackend(
        gateway_url=(
            "http://192.168.1.102:8091"
        ),
        auth_token="a" * 32,
        packager=WorkspacePackager(),
        client=client,
    )

    with pytest.raises(
        SandboxGatewayError,
        match="estado 401",
    ):
        backend.run_pytest(
            create_request(
                create_workspace(tmp_path)
            )
        )


def test_reports_gateway_timeout(
    tmp_path: Path,
) -> None:
    def timeout_handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timeout",
            request=request,
        )

    client = httpx.Client(
        transport=httpx.MockTransport(
            timeout_handler
        )
    )

    backend = HttpSandboxBackend(
        gateway_url=(
            "http://192.168.1.102:8091"
        ),
        auth_token="a" * 32,
        packager=WorkspacePackager(),
        client=client,
    )

    with pytest.raises(
        SandboxGatewayError,
        match="Tiempo agotado",
    ):
        backend.run_pytest(
            create_request(
                create_workspace(tmp_path)
            )
        )

def test_rejects_invalid_http_timeout(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "timeout_seconds debe ser "
            "mayor que cero"
        ),
    ):
        HttpSandboxBackend(
            gateway_url=(
                "http://192.168.1.102:8091"
            ),
            auth_token=(
                "token-seguro-de-prueba-"
                "1234567890"
            ),
            packager=WorkspacePackager(),
            timeout_seconds=0,
        )