from __future__ import annotations

from typing import Protocol
from pathlib import Path

from sandbox_gateway.models import (
    GatewayLimits,
    PytestJobRequest,
    PytestJobResult,
)
from sandbox_gateway.workspace import (
    GatewayWorkspace,
)


class PytestContainerRunner(Protocol):
    def run_pytest(
        self,
        workspace: Path,
        request: PytestJobRequest,
    ) -> PytestJobResult:
        ...


class SandboxGatewayService:
    def __init__(
        self,
        limits: GatewayLimits,
        workspace_manager: GatewayWorkspace,
        container_runner: (
            PytestContainerRunner
        ),
    ) -> None:
        self._limits = limits
        self._workspace_manager = (
            workspace_manager
        )
        self._container_runner = (
            container_runner
        )

    def run_pytest(
        self,
        request: PytestJobRequest,
    ) -> PytestJobResult:
        request.validate(
            self._limits
        )

        with (
            self._workspace_manager
            .materialize(request)
        ) as workspace:
            return (
                self._container_runner
                .run_pytest(
                    workspace=workspace,
                    request=request,
                )
            )