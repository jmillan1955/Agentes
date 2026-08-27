from __future__ import annotations

from dataclasses import dataclass
from pathlib import (
    Path,
    PurePosixPath,
    PureWindowsPath,
)
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SandboxRunRequest:
    workspace_path: Path
    test_target: str
    timeout_seconds: float
    max_output_characters: int

    def __post_init__(self) -> None:
        workspace_path = (
            self.workspace_path.resolve()
        )
        test_target = self.test_target.strip()

        if not test_target:
            raise ValueError(
                "test_target no puede "
                "estar vacio"
            )

        posix_target = PurePosixPath(
            test_target
        )
        windows_target = PureWindowsPath(
            test_target
        )

        if (
            posix_target.is_absolute()
            or windows_target.is_absolute()
            or bool(windows_target.drive)
            or ".." in posix_target.parts
            or ".." in windows_target.parts
        ):
            raise ValueError(
                "test_target debe ser una "
                "ruta relativa segura"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser "
                "mayor que cero"
            )

        if self.max_output_characters <= 0:
            raise ValueError(
                "max_output_characters debe ser "
                "mayor que cero"
            )

        object.__setattr__(
            self,
            "workspace_path",
            workspace_path,
        )
        object.__setattr__(
            self,
            "test_target",
            test_target,
        )


@dataclass(frozen=True, slots=True)
class SandboxRunResult:
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    timed_out: bool
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError(
                "duration_seconds no puede "
                "ser negativo"
            )


class SandboxBackend(Protocol):
    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        ...