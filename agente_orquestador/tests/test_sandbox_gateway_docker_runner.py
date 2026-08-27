import subprocess
from pathlib import Path

from sandbox_gateway.docker_runner import (
    DockerSandboxRunner,
)
from sandbox_gateway.models import (
    GatewayLimits,
    PytestJobRequest,
    SandboxFilePayload,
)


class FakeProcessRunner:
    def __init__(
        self,
        timeout: bool = False,
        stdout: str = "1 passed",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command,
        **kwargs,
    ):
        self.commands.append(command)

        if (
            self.timeout
            and command[1] == "run"
        ):
            raise subprocess.TimeoutExpired(
                command,
                kwargs["timeout"],
            )

        return subprocess.CompletedProcess(
            args=command,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def create_request(
    output_limit: int = 20_000,
) -> PytestJobRequest:
    return PytestJobRequest(
        files=(
            SandboxFilePayload(
                relative_path="test_ok.py",
                content_base64="cHJpbnQoJ29rJyk=",
            ),
        ),
        test_target=".",
        timeout_seconds=30.0,
        max_output_characters=output_limit,
    )


def test_builds_restricted_docker_command(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    process = FakeProcessRunner()

    runner = DockerSandboxRunner(
        image="orchestrator-pytest:3.12",
        limits=GatewayLimits(),
        process_runner=process,
    )

    result = runner.run_pytest(
        workspace=workspace,
        request=create_request(),
    )

    assert result.exit_code == 0
    assert result.timed_out is False

    command = process.commands[0]

    assert command[:2] == [
        "docker",
        "run",
    ]
    assert "--network" in command
    assert "none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert (
        "no-new-privileges:true"
        in command
    )
    assert "65534:65534" in command
    assert "--" in command
    assert command[-1] == "."


def test_removes_container_after_timeout(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    process = FakeProcessRunner(
        timeout=True
    )

    runner = DockerSandboxRunner(
        image="orchestrator-pytest:3.12",
        limits=GatewayLimits(),
        process_runner=process,
    )

    result = runner.run_pytest(
        workspace=workspace,
        request=create_request(),
    )

    assert result.timed_out is True
    assert result.exit_code is None
    assert len(process.commands) == 2
    assert process.commands[1][1:3] == [
        "rm",
        "-f",
    ]


def test_truncates_docker_output(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    process = FakeProcessRunner(
        stdout="123456789",
        stderr="abcdefghi",
    )

    runner = DockerSandboxRunner(
        image="orchestrator-pytest:3.12",
        limits=GatewayLimits(),
        process_runner=process,
    )

    result = runner.run_pytest(
        workspace=workspace,
        request=create_request(
            output_limit=5
        ),
    )

    assert result.stdout_text == "12345"
    assert result.stderr_text == "abcde"