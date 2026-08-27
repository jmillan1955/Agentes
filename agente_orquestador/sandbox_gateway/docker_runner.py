from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from sandbox_gateway.models import (
    GatewayLimits,
    PytestJobRequest,
    PytestJobResult,
)


class DockerSandboxRunner:
    _IMAGE_PATTERN = re.compile(
        r"^[A-Za-z0-9]"
        r"[A-Za-z0-9._/:@-]*$"
    )

    def __init__(
        self,
        image: str,
        limits: GatewayLimits,
        docker_binary: str = "docker",
        process_runner: Callable = (
            subprocess.run
        ),
    ) -> None:
        image = image.strip()
        docker_binary = docker_binary.strip()

        if not self._IMAGE_PATTERN.fullmatch(
            image
        ):
            raise ValueError(
                "La imagen Docker no es valida"
            )

        if not docker_binary:
            raise ValueError(
                "docker_binary no puede "
                "estar vacio"
            )

        self._image = image
        self._limits = limits
        self._docker_binary = docker_binary
        self._process_runner = process_runner

    def run_pytest(
        self,
        workspace: Path,
        request: PytestJobRequest,
    ) -> PytestJobResult:
        request.validate(self._limits)

        workspace = workspace.resolve()

        if not workspace.is_dir():
            raise ValueError(
                "El workspace temporal "
                "no existe"
            )

        container_name = (
            "orchestrator-sandbox-"
            f"{uuid4().hex}"
        )

        command = self._build_command(
            workspace=workspace,
            request=request,
            container_name=container_name,
        )

        started_at = time.monotonic()

        try:
            completed = self._process_runner(
                command,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired:
            self._remove_container(
                container_name
            )

            duration = (
                time.monotonic()
                - started_at
            )

            return PytestJobResult(
                exit_code=None,
                stdout_text="",
                stderr_text=(
                    "La ejecucion supero "
                    "el tiempo maximo"
                ),
                timed_out=True,
                duration_seconds=duration,
            )

        duration = (
            time.monotonic()
            - started_at
        )

        return PytestJobResult(
            exit_code=completed.returncode,
            stdout_text=self._truncate(
                completed.stdout,
                request.max_output_characters,
            ),
            stderr_text=self._truncate(
                completed.stderr,
                request.max_output_characters,
            ),
            timed_out=False,
            duration_seconds=duration,
        )

    def _build_command(
        self,
        workspace: Path,
        request: PytestJobRequest,
        container_name: str,
    ) -> list[str]:
        mount = (
            f"type=bind,src={workspace},"
            "dst=/workspace,readonly"
        )

        return [
            self._docker_binary,
            "run",
            "--name",
            container_name,
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "128",
            "--memory",
            "256m",
            "--cpus",
            "1.0",
            "--user",
            "65534:65534",
            "--tmpfs",
            (
                "/tmp:rw,noexec,nosuid,"
                "size=64m"
            ),
            "--mount",
            mount,
            "--workdir",
            "/workspace",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            self._image,
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--disable-warnings",
            "--",
            request.test_target,
        ]

    def _remove_container(
        self,
        container_name: str,
    ) -> None:
        try:
            self._process_runner(
                [
                    self._docker_binary,
                    "rm",
                    "-f",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        except Exception:
            pass

    @staticmethod
    def _truncate(
        value: str | None,
        limit: int,
    ) -> str:
        return (value or "")[:limit]