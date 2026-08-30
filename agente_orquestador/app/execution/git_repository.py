from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitRepositoryInspectionError(
    RuntimeError
):
    """No se pudo inspeccionar el repositorio Git."""


@dataclass(frozen=True, slots=True)
class GitRepositoryState:
    repository_root: Path
    current_branch: str
    head_commit: str
    is_clean: bool


class GitRepositoryInspector:
    def __init__(
        self,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser "
                "mayor que cero"
            )

        self._timeout_seconds = (
            timeout_seconds
        )

    def inspect(
        self,
        repository_root: Path,
        require_clean: bool = True,
    ) -> GitRepositoryState:
        root_input = (
            repository_root.expanduser()
        )

        if root_input.is_symlink():
            raise GitRepositoryInspectionError(
                "El repositorio no puede ser un "
                "enlace simbolico"
            )

        root = root_input.resolve()

        if not root.is_dir():
            raise GitRepositoryInspectionError(
                "El repositorio no existe"
            )

        actual_root_text = self._run_git(
            repository_root=root,
            arguments=(
                "rev-parse",
                "--show-toplevel",
            ),
        ).strip()

        if not actual_root_text:
            raise GitRepositoryInspectionError(
                "Git no devolvio la raiz del "
                "repositorio"
            )

        actual_root = Path(
            actual_root_text
        ).resolve()

        if actual_root != root:
            raise GitRepositoryInspectionError(
                "La ruta debe ser la raiz exacta "
                "del repositorio Git"
            )

        current_branch = self._run_git(
            repository_root=root,
            arguments=(
                "branch",
                "--show-current",
            ),
        ).strip()

        if not current_branch:
            raise GitRepositoryInspectionError(
                "El repositorio esta en estado "
                "detached HEAD"
            )

        head_commit = self._run_git(
            repository_root=root,
            arguments=(
                "rev-parse",
                "--verify",
                "HEAD",
            ),
        ).strip()

        if not head_commit:
            raise GitRepositoryInspectionError(
                "El repositorio no tiene un "
                "commit inicial"
            )

        status_text = self._run_git(
            repository_root=root,
            arguments=(
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ),
        )

        is_clean = not status_text.strip()

        if require_clean and not is_clean:
            raise GitRepositoryInspectionError(
                "El repositorio objetivo contiene "
                "cambios sin confirmar"
            )

        return GitRepositoryState(
            repository_root=root,
            current_branch=current_branch,
            head_commit=head_commit,
            is_clean=is_clean,
        )

    def _run_git(
        self,
        repository_root: Path,
        arguments: tuple[str, ...],
    ) -> str:
        try:
            result = subprocess.run(
                (
                    "git",
                    "-C",
                    str(repository_root),
                    *arguments,
                ),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
            )

        except FileNotFoundError as error:
            raise GitRepositoryInspectionError(
                "No se encontro el ejecutable Git"
            ) from error

        except subprocess.TimeoutExpired as error:
            raise GitRepositoryInspectionError(
                "Git ha tardado demasiado en "
                "responder"
            ) from error

        except subprocess.CalledProcessError as error:
            detail = (
                error.stderr.strip()
                or error.stdout.strip()
                or "error desconocido"
            )

            raise GitRepositoryInspectionError(
                "Git no pudo inspeccionar el "
                f"repositorio: {detail}"
            ) from error

        return result.stdout