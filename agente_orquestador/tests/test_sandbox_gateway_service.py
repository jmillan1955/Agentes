import base64
from pathlib import Path

from sandbox_gateway.models import (
    GatewayLimits,
    PytestJobRequest,
    PytestJobResult,
    SandboxFilePayload,
)
from sandbox_gateway.service import (
    SandboxGatewayService,
)
from sandbox_gateway.workspace import (
    GatewayWorkspace,
)


class FakeContainerRunner:
    def __init__(self) -> None:
        self.workspace_seen: Path | None = None
        self.file_content: str | None = None

    def run_pytest(
        self,
        workspace: Path,
        request: PytestJobRequest,
    ) -> PytestJobResult:
        self.workspace_seen = workspace

        self.file_content = (
            workspace
            / "tests"
            / "test_temporal.py"
        ).read_text(
            encoding="utf-8"
        )

        return PytestJobResult(
            exit_code=0,
            stdout_text="1 passed",
            stderr_text="",
            timed_out=False,
            duration_seconds=0.1,
        )


def create_request() -> PytestJobRequest:
    content = (
        b"def test_temporal():\n"
        b"    assert True\n"
    )

    return PytestJobRequest(
        files=(
            SandboxFilePayload(
                relative_path=(
                    "tests/test_temporal.py"
                ),
                content_base64=(
                    base64.b64encode(
                        content
                    ).decode("ascii")
                ),
            ),
        ),
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )


def test_runs_materialized_job(
    tmp_path: Path,
) -> None:
    runner = FakeContainerRunner()

    service = SandboxGatewayService(
        limits=GatewayLimits(),
        workspace_manager=(
            GatewayWorkspace(
                temporary_root=tmp_path
            )
        ),
        container_runner=runner,
    )

    result = service.run_pytest(
        create_request()
    )

    assert result.exit_code == 0
    assert result.stdout_text == "1 passed"
    assert runner.workspace_seen is not None
    assert runner.file_content == (
        "def test_temporal():\n"
        "    assert True\n"
    )

    assert (
        runner.workspace_seen.exists()
        is False
    )