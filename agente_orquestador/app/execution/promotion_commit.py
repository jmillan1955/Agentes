from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.execution.git_repository import (
    GitRepositoryInspectionError,
    GitRepositoryInspector,
)
from app.execution.promotion_validation import (
    PromotionValidationResult,
)


class PromotionCommitError(
    RuntimeError
):
    """No se pudo confirmar la promocion en Git."""


@dataclass(frozen=True, slots=True)
class PromotionCommitResult:
    repository_root: Path
    branch_name: str
    base_commit: str
    commit_hash: str
    commit_message: str
    committed_paths: tuple[str, ...]


class PromotionCommitService:
    def __init__(
        self,
        git_inspector: GitRepositoryInspector,
        timeout_seconds: float = 20.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser "
                "mayor que cero"
            )

        self._git_inspector = git_inspector
        self._timeout_seconds = (
            timeout_seconds
        )

    def commit(
        self,
        execution_id: int,
        validation: PromotionValidationResult,
    ) -> PromotionCommitResult:
        if execution_id <= 0:
            raise PromotionCommitError(
                "execution_id debe ser mayor "
                "que cero"
            )

        sandbox_result = (
            validation.sandbox_result
        )

        if (
            sandbox_result.timed_out
            or sandbox_result.exit_code != 0
        ):
            raise PromotionCommitError(
                "La promocion no tiene una "
                "validacion satisfactoria"
            )

        workflow = validation.workflow_result
        branch = workflow.branch
        application = workflow.application
        repository_root = (
            branch.repository_root.resolve()
        )

        try:
            state = self._git_inspector.inspect(
                repository_root=repository_root,
                require_clean=False,
            )

        except GitRepositoryInspectionError as error:
            raise PromotionCommitError(
                str(error)
            ) from error

        if (
            state.current_branch
            != branch.promotion_branch
            or state.current_branch
            != application.branch_name
        ):
            raise PromotionCommitError(
                "La rama activa no es la rama "
                "temporal validada"
            )

        if (
            state.head_commit
            != branch.base_commit
            or state.head_commit
            != application.head_commit
        ):
            raise PromotionCommitError(
                "El commit base cambio despues "
                "de la validacion"
            )

        expected_paths = tuple(
            sorted(application.written_paths)
        )
        changed_paths = (
            self._get_changed_paths(
                repository_root
            )
        )

        if changed_paths != expected_paths:
            raise PromotionCommitError(
                "El repositorio contiene cambios "
                "distintos de los promocionados"
            )

        if not changed_paths:
            raise PromotionCommitError(
                "No existen cambios para confirmar"
            )

        commit_message = (
            "Promocionar ejecucion "
            f"#{execution_id}"
        )

        try:
            self._run_git(
                repository_root=repository_root,
                arguments=(
                    "add",
                    "--",
                    *changed_paths,
                ),
            )

            self._run_git(
                repository_root=repository_root,
                arguments=(
                    "commit",
                    "-m",
                    commit_message,
                ),
            )

        except PromotionCommitError:
            self._unstage_after_failure(
                repository_root
            )
            raise

        try:
            final_state = (
                self._git_inspector.inspect(
                    repository_root
                )
            )

        except GitRepositoryInspectionError as error:
            raise PromotionCommitError(
                str(error)
            ) from error

        if (
            final_state.current_branch
            != branch.promotion_branch
        ):
            raise PromotionCommitError(
                "Git cambio de rama durante "
                "el commit"
            )

        if (
            final_state.head_commit
            == branch.base_commit
        ):
            raise PromotionCommitError(
                "Git no creo el commit de "
                "promocion"
            )

        parent_commit = self._run_git(
            repository_root=repository_root,
            arguments=(
                "rev-parse",
                "HEAD^",
            ),
        ).strip()

        if parent_commit != branch.base_commit:
            raise PromotionCommitError(
                "El commit no parte del commit "
                "base esperado"
            )

        committed_paths = tuple(
            sorted(
                path
                for path in self._run_git(
                    repository_root=(
                        repository_root
                    ),
                    arguments=(
                        "show",
                        "--pretty=format:",
                        "--name-only",
                        "HEAD",
                    ),
                ).splitlines()
                if path.strip()
            )
        )

        if committed_paths != expected_paths:
            raise PromotionCommitError(
                "El commit contiene archivos "
                "distintos de los esperados"
            )

        return PromotionCommitResult(
            repository_root=repository_root,
            branch_name=(
                final_state.current_branch
            ),
            base_commit=branch.base_commit,
            commit_hash=(
                final_state.head_commit
            ),
            commit_message=commit_message,
            committed_paths=committed_paths,
        )

    def _get_changed_paths(
        self,
        repository_root: Path,
    ) -> tuple[str, ...]:
        status_text = self._run_git(
            repository_root=repository_root,
            arguments=(
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ),
        )

        paths: list[str] = []

        for entry in status_text.split("\0"):
            if not entry:
                continue

            if len(entry) < 4:
                raise PromotionCommitError(
                    "Git devolvio un estado "
                    "no valido"
                )

            status = entry[:2]
            relative_path = entry[3:]

            if (
                not relative_path
                or status == "!!"
                or "D" in status
                or "R" in status
                or "C" in status
            ):
                raise PromotionCommitError(
                    "El repositorio contiene un "
                    "cambio no autorizado"
                )

            paths.append(relative_path)

        if len(paths) != len(set(paths)):
            raise PromotionCommitError(
                "Git devolvio rutas duplicadas"
            )

        return tuple(sorted(paths))

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
            raise PromotionCommitError(
                "No se encontro el ejecutable Git"
            ) from error

        except subprocess.TimeoutExpired as error:
            raise PromotionCommitError(
                "Git ha tardado demasiado en "
                "responder"
            ) from error

        except subprocess.CalledProcessError as error:
            detail = (
                error.stderr.strip()
                or error.stdout.strip()
                or "error desconocido"
            )

            raise PromotionCommitError(
                "Git no pudo confirmar la "
                f"promocion: {detail}"
            ) from error

        return result.stdout

    def _unstage_after_failure(
        self,
        repository_root: Path,
    ) -> None:
        try:
            subprocess.run(
                (
                    "git",
                    "-C",
                    str(repository_root),
                    "reset",
                    "--quiet",
                ),
                check=False,
                capture_output=True,
                timeout=self._timeout_seconds,
            )

        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return