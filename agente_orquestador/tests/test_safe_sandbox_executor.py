from pathlib import Path

import pytest

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)
from app.execution.sandbox_executor import (
    SafeSandboxExecutor,
    SandboxActionExecutionError,
)


class FakeSandboxBackend:
    def __init__(
        self,
        result: SandboxRunResult,
    ) -> None:
        self.result = result
        self.requests: list[
            SandboxRunRequest
        ] = []

    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        self.requests.append(request)
        return self.result


def create_action() -> ExecutionAction:
    return ExecutionAction(
        step_number=1,
        name="Ejecutar pruebas",
        action_type=(
            ExecutionActionType.RUN_PYTEST
        ),
        relative_path="tests",
    )


def test_runs_pytest_with_safe_limits(
    tmp_path: Path,
) -> None:
    backend = FakeSandboxBackend(
        SandboxRunResult(
            exit_code=0,
            stdout_text="3 passed",
            stderr_text="",
            timed_out=False,
            duration_seconds=0.5,
        )
    )
    executor = SafeSandboxExecutor(
        backend=backend,
        limits=ExecutionLimits(
            command_timeout_seconds=30,
            max_output_characters=100,
        ),
    )

    result = executor.execute(
        workspace_path=tmp_path,
        action=create_action(),
    )

    assert result.exit_code == 0
    assert result.stdout_text == "3 passed"
    assert len(backend.requests) == 1
    assert (
        backend.requests[0].timeout_seconds
        == 30
    )


def test_rejects_failed_pytest(
    tmp_path: Path,
) -> None:
    backend = FakeSandboxBackend(
        SandboxRunResult(
            exit_code=1,
            stdout_text="1 failed",
            stderr_text="error",
            timed_out=False,
            duration_seconds=0.4,
        )
    )
    executor = SafeSandboxExecutor(
        backend=backend,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        SandboxActionExecutionError,
        match="finalizo con errores",
    ) as captured:
        executor.execute(
            workspace_path=tmp_path,
            action=create_action(),
        )

    assert captured.value.result.exit_code == 1


def test_rejects_timeout(
    tmp_path: Path,
) -> None:
    backend = FakeSandboxBackend(
        SandboxRunResult(
            exit_code=None,
            stdout_text="",
            stderr_text="timeout",
            timed_out=True,
            duration_seconds=60.0,
        )
    )
    executor = SafeSandboxExecutor(
        backend=backend,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        SandboxActionExecutionError,
        match="tiempo maximo",
    ):
        executor.execute(
            workspace_path=tmp_path,
            action=create_action(),
        )


def test_truncates_sandbox_output(
    tmp_path: Path,
) -> None:
    backend = FakeSandboxBackend(
        SandboxRunResult(
            exit_code=0,
            stdout_text="123456789",
            stderr_text="abcdefghi",
            timed_out=False,
            duration_seconds=0.1,
        )
    )
    executor = SafeSandboxExecutor(
        backend=backend,
        limits=ExecutionLimits(
            max_output_characters=5
        ),
    )

    result = executor.execute(
        workspace_path=tmp_path,
        action=create_action(),
    )

    assert result.stdout_text == "12345"
    assert result.stderr_text == "abcde"