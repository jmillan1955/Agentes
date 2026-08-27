from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.workspace import (
    WorkspacePolicy,
)


class FilesystemExecutionError(
    RuntimeError
):
    """No se pudo ejecutar la accion."""


@dataclass(frozen=True, slots=True)
class FilesystemActionResult:
    target_path: Path
    created: bool
    bytes_written: int
    message: str


class SafeFilesystemExecutor:
    def __init__(
        self,
        workspace_policy: WorkspacePolicy,
        limits: ExecutionLimits,
    ) -> None:
        self._workspace_policy = (
            workspace_policy
        )
        self._limits = limits

    def execute(
        self,
        workspace_path: Path,
        action: ExecutionAction,
    ) -> FilesystemActionResult:
        target = (
            self._workspace_policy
            .resolve_target(
                workspace_path=workspace_path,
                relative_path=(
                    action.relative_path
                ),
            )
        )

        if (
            action.action_type
            == ExecutionActionType
            .CREATE_DIRECTORY
        ):
            return self._create_directory(
                target
            )

        if (
            action.action_type
            == ExecutionActionType
            .WRITE_TEXT_FILE
        ):
            return self._write_text_file(
                target=target,
                content=action.content,
            )

        raise FilesystemExecutionError(
            "Tipo de accion no autorizado"
        )

    @staticmethod
    def _create_directory(
        target: Path,
    ) -> FilesystemActionResult:
        existed = target.exists()

        if existed and not target.is_dir():
            raise FilesystemExecutionError(
                "La ruta existe y no es "
                "un directorio"
            )

        target.mkdir(
            parents=True,
            exist_ok=True,
        )

        return FilesystemActionResult(
            target_path=target,
            created=not existed,
            bytes_written=0,
            message=(
                "Directorio creado"
                if not existed
                else "Directorio ya existente"
            ),
        )

    def _write_text_file(
        self,
        target: Path,
        content: str | None,
    ) -> FilesystemActionResult:
        if content is None:
            raise FilesystemExecutionError(
                "La accion no contiene texto"
            )

        encoded = content.encode("utf-8")

        if (
            len(encoded)
            > self._limits.max_text_file_bytes
        ):
            raise FilesystemExecutionError(
                "El archivo supera el limite "
                "de tamano"
            )

        if not target.parent.is_dir():
            raise FilesystemExecutionError(
                "El directorio padre no existe"
            )

        if target.exists():
            if not target.is_file():
                raise FilesystemExecutionError(
                    "La ruta existe y no es "
                    "un archivo"
                )

            existing = target.read_text(
                encoding="utf-8"
            )

            if existing != content:
                raise FilesystemExecutionError(
                    "No se permite sobrescribir "
                    "un archivo con contenido "
                    "diferente"
                )

            return FilesystemActionResult(
                target_path=target,
                created=False,
                bytes_written=0,
                message=(
                    "Archivo ya existente "
                    "sin cambios"
                ),
            )

        target.write_text(
            content,
            encoding="utf-8",
            newline="",
        )

        return FilesystemActionResult(
            target_path=target,
            created=True,
            bytes_written=len(encoded),
            message="Archivo creado",
        )