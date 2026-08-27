import base64

from fastapi.testclient import TestClient

from sandbox_gateway.api import create_app
from sandbox_gateway.models import (
    PytestJobResult,
)


class FakeGatewayService:
    def __init__(self) -> None:
        self.calls = 0

    def run_pytest(self, request):
        self.calls += 1

        return PytestJobResult(
            exit_code=0,
            stdout_text="1 passed",
            stderr_text="",
            timed_out=False,
            duration_seconds=0.1,
        )


def create_payload() -> dict:
    content = base64.b64encode(
        b"def test_ok(): pass\n"
    ).decode("ascii")

    return {
        "files": [
            {
                "relative_path": (
                    "tests/test_ok.py"
                ),
                "content_base64": content,
            }
        ],
        "test_target": "tests",
        "timeout_seconds": 60.0,
        "max_output_characters": 20_000,
    }


def test_health_is_public() -> None:
    service = FakeGatewayService()
    client = TestClient(
        create_app(
            service=service,
            auth_token="a" * 32,
        )
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok"
    }


def test_rejects_unauthorized_job() -> None:
    service = FakeGatewayService()
    client = TestClient(
        create_app(
            service=service,
            auth_token="a" * 32,
        )
    )

    response = client.post(
        "/v1/pytest",
        json=create_payload(),
    )

    assert response.status_code == 401
    assert service.calls == 0


def test_runs_authorized_job() -> None:
    service = FakeGatewayService()
    client = TestClient(
        create_app(
            service=service,
            auth_token="a" * 32,
        )
    )

    response = client.post(
        "/v1/pytest",
        json=create_payload(),
        headers={
            "Authorization": (
                f"Bearer {'a' * 32}"
            )
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["stdout_text"]
        == "1 passed"
    )
    assert service.calls == 1