from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from pathlib import (
    PurePosixPath,
    PureWindowsPath,
)


def validate_relative_path(
    value: str,
    field_name: str,
) -> str:
    value = value.strip()

    if not value:
        raise ValueError(
            f"{field_name} no puede "
            "estar vacio"
        )

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)

    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise ValueError(
            f"{field_name} debe ser una "
            "ruta relativa segura"
        )

    return value


@dataclass(frozen=True, slots=True)
class GatewayLimits:
    max_files: int = 200
    max_total_bytes: int = 10_000_000
    max_timeout_seconds: float = 120.0
    max_output_characters: int = 50_000

    def __post_init__(self) -> None:
        for field_name in (
            "max_files",
            "max_total_bytes",
            "max_output_characters",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero"
                )

        if self.max_timeout_seconds <= 0:
            raise ValueError(
                "max_timeout_seconds debe ser "
                "mayor que cero"
            )


@dataclass(frozen=True, slots=True)
class SandboxFilePayload:
    relative_path: str
    content_base64: str

    def __post_init__(self) -> None:
        relative_path = (
            validate_relative_path(
                self.relative_path,
                "relative_path",
            )
        )

        content_base64 = (
            self.content_base64.strip()
        )

        if not content_base64:
            raise ValueError(
                "content_base64 no puede "
                "estar vacio"
            )

        try:
            base64.b64decode(
                content_base64,
                validate=True,
            )

        except (
            binascii.Error,
            ValueError,
        ) as error:
            raise ValueError(
                "content_base64 no es valido"
            ) from error

        object.__setattr__(
            self,
            "relative_path",
            relative_path,
        )
        object.__setattr__(
            self,
            "content_base64",
            content_base64,
        )

    def decode(self) -> bytes:
        return base64.b64decode(
            self.content_base64,
            validate=True,
        )


@dataclass(frozen=True, slots=True)
class PytestJobRequest:
    files: tuple[SandboxFilePayload, ...]
    test_target: str
    timeout_seconds: float
    max_output_characters: int

    def validate(
        self,
        limits: GatewayLimits,
    ) -> None:
        if not self.files:
            raise ValueError(
                "El trabajo no contiene archivos"
            )

        if len(self.files) > limits.max_files:
            raise ValueError(
                "El trabajo supera el numero "
                "maximo de archivos"
            )

        validate_relative_path(
            self.test_target,
            "test_target",
        )

        if (
            self.timeout_seconds <= 0
            or self.timeout_seconds
            > limits.max_timeout_seconds
        ):
            raise ValueError(
                "timeout_seconds queda fuera "
                "del limite permitido"
            )

        if (
            self.max_output_characters <= 0
            or self.max_output_characters
            > limits.max_output_characters
        ):
            raise ValueError(
                "max_output_characters queda "
                "fuera del limite permitido"
            )

        paths = tuple(
            file.relative_path
            for file in self.files
        )

        if len(set(paths)) != len(paths):
            raise ValueError(
                "El trabajo contiene rutas "
                "duplicadas"
            )

        total_bytes = sum(
            len(file.decode())
            for file in self.files
        )

        if total_bytes > limits.max_total_bytes:
            raise ValueError(
                "El trabajo supera el tamano "
                "maximo permitido"
            )


@dataclass(frozen=True, slots=True)
class PytestJobResult:
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    timed_out: bool
    duration_seconds: float