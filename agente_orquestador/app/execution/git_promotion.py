from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.execution.git_repository import (
    GitRepositoryInspectionError,
    GitRepositoryInspector,
)


class GitPromotionError(
    RuntimeError
):
    """No se pudo gestionar la rama de promocion."""


@dataclass(frozen=True, slots=True)
class GitPromotionBranch:
    repository_root: Path
    base_branch: str
    promotion_branch: str
    base_commit: str


class GitPromotionBranchService:
    _BRANCH_PREFIX = "promotion/"

    def __init__(
        self,
        git_inspector: GitRepositoryInspector,
        timeout_seconds: float = 10.0,
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

    def create(
        self,
        repository_root: Path,
        branch_name: str,
    ) -> GitPromotionBranch:
        normalized_branch = (
            self._validate_branch_name(
                branch_name
            )
        )

        try:
            initial_state = (
                self._git_inspector.inspect(
                    repository_root
                )
            )

        except GitRepositoryInspectionError as error:
            raise GitPromotionError(
                str(error)
            ) from error

        root = initial_state.repository_root

        if self._branch_exists(
            repository_root=root,
            branch_name=normalized_branch,
        ):
            raise GitPromotionError(
                "La rama de promocion ya existe"
            )

        try:
            self._run_git(
                repository_root=root,
                arguments=(
                    "switch",
                    "-c",
                    normalized_branch,
                ),
            )

            final_state = (
                self._git_inspector.inspect(
                    root
                )
            )

            if (
                final_state.current_branch
                != normalized_branch
                or final_state.head_commit
                != initial_state.head_commit
            ):
                raise GitPromotionError(
                    "Git no creo la rama desde el "
                    "commit esperado"
                )

        except Exception as error:
            self._restore_after_create_failure(
                repository_root=root,
                base_branch=(
                    initial_state.current_branch
                ),
                promotion_branch=(
                    normalized_branch
                ),
            )

            if isinstance(
                error,
                GitPromotionError,
            ):
                raise

            if isinstance(
                error,
                GitRepositoryInspectionError,
            ):
                raise GitPromotionError(
                    str(error)
                ) from error

            raise

        return GitPromotionBranch(
            repository_root=root,
            base_branch=(
                initial_state.current_branch
            ),
            promotion_branch=(
                normalized_branch
            ),
            base_commit=(
                initial_state.head_commit
            ),
        )

    def rollback(
        self,
        branch: GitPromotionBranch,
    ) -> None:
        try:
            state = self._git_inspector.inspect(
                branch.repository_root
            )

        except GitRepositoryInspectionError as error:
            raise GitPromotionError(
                str(error)
            ) from error

        if (
            state.current_branch
            != branch.promotion_branch
        ):
            raise GitPromotionError(
                "La rama activa no es la rama "
                "de promocion"
            )

        if state.head_commit != branch.base_commit:
            raise GitPromotionError(
                "La rama de promocion contiene "
                "commits y no puede eliminarse"
            )

        self._run_git(
            repository_root=(
                branch.repository_root
            ),
            arguments=(
                "switch",
                branch.base_branch,
            ),
        )

        try:
            self._run_git(
                repository_root=(
                    branch.repository_root
                ),
                arguments=(
                    "branch",
                    "-D",
                    branch.promotion_branch,
                ),
            )

        except GitPromotionError:
            self._run_git(
                repository_root=(
                    branch.repository_root
                ),
                arguments=(
                    "switch",
                    branch.promotion_branch,
                ),
            )
            raise

    def _validate_branch_name(
        self,
        branch_name: str,
    ) -> str:
        normalized = branch_name.strip()

        if (
            not normalized
            or normalized != branch_name
            or not normalized.startswith(
                self._BRANCH_PREFIX
            )
        ):
            raise GitPromotionError(
                "El nombre de rama debe comenzar "
                "por promotion/"
            )

        self._run_git(
            repository_root=None,
            arguments=(
                "check-ref-format",
                "--branch",
                normalized,
            ),
        )

        return normalized

    def _branch_exists(
        self,
        repository_root: Path,
        branch_name: str,
    ) -> bool:
        output = self._run_git(
            repository_root=repository_root,
            arguments=(
                "branch",
                "--list",
                "--format=%(refname:short)",
                branch_name,
            ),
        )

        return output.strip() == branch_name

    def _restore_after_create_failure(
        self,
        repository_root: Path,
        base_branch: str,
        promotion_branch: str,
    ) -> None:
        try:
            current_branch = self._run_git(
                repository_root=repository_root,
                arguments=(
                    "branch",
                    "--show-current",
                ),
            ).strip()

            if current_branch == promotion_branch:
                self._run_git(
                    repository_root=(
                        repository_root
                    ),
                    arguments=(
                        "switch",
                        base_branch,
                    ),
                )

            if self._branch_exists(
                repository_root=repository_root,
                branch_name=promotion_branch,
            ):
                self._run_git(
                    repository_root=(
                        repository_root
                    ),
                    arguments=(
                        "branch",
                        "-D",
                        promotion_branch,
                    ),
                )

        except GitPromotionError:
            return

    def _run_git(
        self,
        repository_root: Path | None,
        arguments: tuple[str, ...],
    ) -> str:
        command = ["git"]

        if repository_root is not None:
            command.extend(
                (
                    "-C",
                    str(repository_root),
                )
            )

        command.extend(arguments)

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
            )

        except FileNotFoundError as error:
            raise GitPromotionError(
                "No se encontro el ejecutable Git"
            ) from error

        except subprocess.TimeoutExpired as error:
            raise GitPromotionError(
                "Git ha tardado demasiado en "
                "responder"
            ) from error

        except subprocess.CalledProcessError as error:
            detail = (
                error.stderr.strip()
                or error.stdout.strip()
                or "error desconocido"
            )

            raise GitPromotionError(
                "Git no pudo gestionar la rama: "
                f"{detail}"
            ) from error

        return result.stdout