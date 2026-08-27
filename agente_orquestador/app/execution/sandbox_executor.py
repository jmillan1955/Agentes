from __future__ import annotations

from pathlib import Path

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.sandbox import (
    SandboxBackend,
    SandboxRunRequest,
    SandboxRunResult,
)


class SandboxActionExecutionError(
    RuntimeError
):
    def __init__(
        self,
        message: str,
        result: SandboxRunResult,
    ) -> None:
        super().__init__(message)
        self.result = result


class SafeSandboxExecutor:
    def __init__(
        self,
        backend: SandboxBackend,
        limits: ExecutionLimits,
    ) -> None:
        self._backend = backend
        self._limits = limits

    def execute(
        self,
        workspace_path: Path,
        action: ExecutionAction,
    ) -> SandboxRunResult:
        if (
            action.action_type
            != ExecutionActionType.RUN_PYTEST
        ):
            raise ValueError(
                "El sandbox solo admite "
                "run_pytest"
            )

        request = SandboxRunRequest(
            workspace_path=workspace_path,
            test_target=action.relative_path,
            timeout_seconds=(
                self._limits
                .command_timeout_seconds
            ),
            max_output_characters=(
                self._limits
                .max_output_characters
            ),
        )

        raw_result = self._backend.run_pytest(
            request
        )

        result = SandboxRunResult(
            exit_code=raw_result.exit_code,
            stdout_text=self._truncate(
                raw_result.stdout_text
            ),
            stderr_text=self._truncate(
                raw_result.stderr_text
            ),
            timed_out=raw_result.timed_out,
            duration_seconds=(
                raw_result.duration_seconds
            ),
        )

        if result.timed_out:
            raise SandboxActionExecutionError(
                "La ejecucion de pytest supero "
                "el tiempo maximo",
                result,
            )

        if result.exit_code != 0:
            raise SandboxActionExecutionError(
                "Pytest finalizo con errores",
                result,
            )

        return result

    def _truncate(
        self,
        text: str,
    ) -> str:
        limit = (
            self._limits
            .max_output_characters
        )

        return text[:limit]