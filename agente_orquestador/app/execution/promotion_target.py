from __future__ import annotations

from dataclasses import dataclass
from pathlib import (
    Path,
    PurePosixPath,
)

from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.context.task_repository import (
    TaskRepository,
)
from app.execution.git_repository import (
    GitRepositoryInspectionError,
    GitRepositoryInspector,
)
from app.execution.promotion_paths import (
    PromotionPathError,
    normalize_target_subdirectory,
)


class PromotionTargetResolutionError(
    RuntimeError
):
    """No se pudo resolver el destino autorizado."""


@dataclass(frozen=True, slots=True)
class PromotionTarget:
    execution_id: int
    repository_root: Path
    target_project_name: str
    target_subdirectory: str
    test_target: str


class PromotionTargetResolver:
    def __init__(
        self,
        execution_repository: (
            TaskExecutionRepository
        ),
        task_repository: TaskRepository,
        git_inspector: GitRepositoryInspector,
        repository_root: Path,
        allowed_projects: dict[str, str],
        test_target: str = ".",
    ) -> None:
        normalized_projects: dict[
            str,
            str,
        ] = {}

        for project_name, subdirectory in (
            allowed_projects.items()
        ):
            normalized_name = (
                project_name.strip()
            )

            if not normalized_name:
                raise ValueError(
                    "El nombre de un proyecto "
                    "autorizado no puede estar "
                    "vacio"
                )

            if normalized_name in (
                normalized_projects
            ):
                raise ValueError(
                    "La lista contiene proyectos "
                    "duplicados"
                )

            try:
                normalized_subdirectory = (
                    normalize_target_subdirectory(
                        subdirectory
                    )
                )

            except PromotionPathError as error:
                raise ValueError(
                    "Un subdirectorio autorizado "
                    f"no es valido: {error}"
                ) from error

            if normalized_subdirectory == ".":
                raise ValueError(
                    "Un proyecto objetivo no puede "
                    "usar la raiz completa"
                )

            normalized_projects[
                normalized_name
            ] = normalized_subdirectory

        normalized_test_target = (
            test_target.strip()
        )

        if not normalized_test_target:
            raise ValueError(
                "test_target no puede estar "
                "vacio"
            )

        self._execution_repository = (
            execution_repository
        )
        self._task_repository = (
            task_repository
        )
        self._git_inspector = git_inspector
        self._repository_root = repository_root
        self._allowed_projects = (
            normalized_projects
        )
        self._test_target = (
            normalized_test_target
        )

    def resolve_task(
        self,
        task_id: int,
    ) -> PromotionTarget:
        if task_id <= 0:
            raise PromotionTargetResolutionError(
                "task_id debe ser mayor que cero"
            )

        execution = (
            self._execution_repository
            .get_by_task_id(task_id)
        )

        if execution is None:
            raise PromotionTargetResolutionError(
                "La tarea no tiene una "
                "ejecucion preparada"
            )

        return self.resolve(
            execution.id
        )

    def resolve(
        self,
        execution_id: int,
    ) -> PromotionTarget:
        if execution_id <= 0:
            raise PromotionTargetResolutionError(
                "execution_id debe ser mayor "
                "que cero"
            )

        execution = (
            self._execution_repository
            .get_by_id(execution_id)
        )

        if execution is None:
            raise PromotionTargetResolutionError(
                "No existe la ejecucion"
            )

        task = self._task_repository.get_by_id(
            execution.task_id
        )

        if task is None:
            raise PromotionTargetResolutionError(
                "No existe la tarea asociada"
            )

        target_project_name = (
            task.target_project_name
        )

        if target_project_name is None:
            raise PromotionTargetResolutionError(
                "La tarea no identifica un "
                "proyecto objetivo"
            )

        target_project_name = (
            target_project_name.strip()
        )

        target_subdirectory = (
            self._allowed_projects.get(
                target_project_name
            )
        )

        if target_subdirectory is None:
            raise PromotionTargetResolutionError(
                "El proyecto objetivo no esta "
                "autorizado para promociones"
            )

        try:
            repository_state = (
                self._git_inspector.inspect(
                    repository_root=(
                        self._repository_root
                    ),
                    require_clean=True,
                )
            )

        except GitRepositoryInspectionError as error:
            raise PromotionTargetResolutionError(
                str(error)
            ) from error

        repository_root = (
            repository_state
            .repository_root
            .resolve()
        )

        relative = PurePosixPath(
            target_subdirectory
        )
        target_path = repository_root.joinpath(
            *relative.parts
        )

        current = target_path

        while current != repository_root:
            if current.is_symlink():
                raise PromotionTargetResolutionError(
                    "El destino autorizado "
                    "contiene un enlace simbolico"
                )

            current = current.parent

        resolved_target = target_path.resolve()

        if not resolved_target.is_relative_to(
            repository_root
        ):
            raise PromotionTargetResolutionError(
                "El destino autorizado sale del "
                "repositorio"
            )

        if (
            resolved_target.exists()
            and not resolved_target.is_dir()
        ):
            raise PromotionTargetResolutionError(
                "El destino autorizado no es un "
                "directorio"
            )

        return PromotionTarget(
            execution_id=execution.id,
            repository_root=repository_root,
            target_project_name=(
                target_project_name
            ),
            target_subdirectory=(
                target_subdirectory
            ),
            test_target=self._test_target,
        )