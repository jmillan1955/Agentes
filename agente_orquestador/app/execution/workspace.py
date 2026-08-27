from __future__ import annotations

import re
from pathlib import Path


class WorkspaceViolationError(
    ValueError
):
    """Ruta de ejecucion no permitida."""


class WorkspacePolicy:
    _PROJECT_NAME_PATTERN = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )

    def __init__(
        self,
        allowed_root: Path,
        protected_paths: tuple[
            Path,
            ...,
        ] = (),
    ) -> None:
        self._allowed_root = (
            allowed_root.expanduser().resolve()
        )

        self._protected_paths = tuple(
            path.expanduser().resolve()
            for path in protected_paths
        )

    @property
    def allowed_root(self) -> Path:
        return self._allowed_root

    def resolve(
        self,
        project_name: str,
    ) -> Path:
        project_name = project_name.strip()

        if not project_name:
            raise WorkspaceViolationError(
                "El nombre del proyecto no puede "
                "estar vacio"
            )

        if not self._PROJECT_NAME_PATTERN.fullmatch(
            project_name
        ):
            raise WorkspaceViolationError(
                "El nombre del proyecto contiene "
                "caracteres no permitidos"
            )

        candidate = (
            self._allowed_root / project_name
        ).resolve()

        if not candidate.is_relative_to(
            self._allowed_root
        ):
            raise WorkspaceViolationError(
                "El workspace queda fuera de "
                "la raiz permitida"
            )

        for protected_path in (
            self._protected_paths
        ):
            if (
                candidate == protected_path
                or candidate.is_relative_to(
                    protected_path
                )
            ):
                raise WorkspaceViolationError(
                    "El workspace coincide con "
                    "una ruta protegida"
                )

        if (
            candidate.exists()
            and not candidate.is_dir()
        ):
            raise WorkspaceViolationError(
                "El workspace existente no es "
                "un directorio"
            )

        return candidate

    def resolve_target(
        self,
        workspace_path: Path,
        relative_path: str,
    ) -> Path:
        workspace = (
            workspace_path
            .expanduser()
            .resolve()
        )

        if (
            workspace == self._allowed_root
            or not workspace.is_relative_to(
                self._allowed_root
            )
        ):
            raise WorkspaceViolationError(
                "El workspace no es un proyecto "
                "permitido"
            )

        relative_path = relative_path.strip()

        if not relative_path:
            raise WorkspaceViolationError(
                "La ruta relativa no puede "
                "estar vacia"
            )

        relative = Path(relative_path)

        if relative.is_absolute():
            raise WorkspaceViolationError(
                "La ruta de destino no puede "
                "ser absoluta"
            )

        candidate = (
            workspace / relative
        ).resolve()

        if not candidate.is_relative_to(
            workspace
        ):
            raise WorkspaceViolationError(
                "La ruta de destino queda fuera "
                "del workspace"
            )

        for protected_path in (
            self._protected_paths
        ):
            if (
                candidate == protected_path
                or candidate.is_relative_to(
                    protected_path
                )
            ):
                raise WorkspaceViolationError(
                    "La ruta de destino coincide "
                    "con una ruta protegida"
                )

        return candidate