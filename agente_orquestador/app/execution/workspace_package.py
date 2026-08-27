from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path


class WorkspacePackagingError(
    RuntimeError
):
    """No se puede empaquetar el workspace."""


@dataclass(frozen=True, slots=True)
class PackagedWorkspaceFile:
    relative_path: str
    content_base64: str
    size_bytes: int


class WorkspacePackager:
    _ALLOWED_SUFFIXES = {
        ".py",
        ".toml",
        ".ini",
        ".cfg",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".md",
    }

    _EXCLUDED_PARTS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
    }

    _EXCLUDED_NAMES = {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519",
    }

    def __init__(
        self,
        max_files: int = 200,
        max_total_bytes: int = 10_000_000,
    ) -> None:
        if max_files <= 0:
            raise ValueError(
                "max_files debe ser "
                "mayor que cero"
            )

        if max_total_bytes <= 0:
            raise ValueError(
                "max_total_bytes debe ser "
                "mayor que cero"
            )

        self._max_files = max_files
        self._max_total_bytes = (
            max_total_bytes
        )

    def package(
        self,
        workspace_path: Path,
    ) -> tuple[PackagedWorkspaceFile, ...]:
        workspace = (
            workspace_path.resolve()
        )

        if not workspace.is_dir():
            raise WorkspacePackagingError(
                "El workspace no existe"
            )

        packaged: list[
            PackagedWorkspaceFile
        ] = []
        total_bytes = 0

        for path in sorted(
            workspace.rglob("*")
        ):
            relative = path.relative_to(
                workspace
            )

            if any(
                part in self._EXCLUDED_PARTS
                for part in relative.parts
            ):
                continue

            if path.is_symlink():
                raise WorkspacePackagingError(
                    "El workspace contiene "
                    "un enlace simbolico"
                )

            if not path.is_file():
                continue

            if path.name in self._EXCLUDED_NAMES:
                continue

            if (
                path.suffix.lower()
                not in self._ALLOWED_SUFFIXES
            ):
                continue

            content = path.read_bytes()
            total_bytes += len(content)

            if (
                len(packaged) + 1
                > self._max_files
            ):
                raise WorkspacePackagingError(
                    "El workspace supera el "
                    "numero maximo de archivos"
                )

            if (
                total_bytes
                > self._max_total_bytes
            ):
                raise WorkspacePackagingError(
                    "El workspace supera el "
                    "tamano maximo"
                )

            packaged.append(
                PackagedWorkspaceFile(
                    relative_path=(
                        relative.as_posix()
                    ),
                    content_base64=(
                        base64.b64encode(
                            content
                        ).decode("ascii")
                    ),
                    size_bytes=len(content),
                )
            )

        if not packaged:
            raise WorkspacePackagingError(
                "El workspace no contiene "
                "archivos permitidos"
            )

        return tuple(packaged)