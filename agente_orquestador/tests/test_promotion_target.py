from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.git_repository import (
    GitRepositoryInspectionError,
)
from app.execution.promotion_target import (
    PromotionTargetResolutionError,
    PromotionTargetResolver,
)


def create_resolver(
    repository_root: Path,
    target_project_name: (
        str | None
    ) = "puntuacion_padel",
    allowed_projects: (
        dict[str, str] | None
    ) = None,
):
    execution_repository = Mock()
    task_repository = Mock()
    git_inspector = Mock()

    execution_repository.get_by_id.return_value = (
        SimpleNamespace(
            id=7,
            task_id=3,
        )
    )
    task_repository.get_by_id.return_value = (
        SimpleNamespace(
            id=3,
            target_project_name=(
                target_project_name
            ),
        )
    )
    git_inspector.inspect.return_value = (
        SimpleNamespace(
            repository_root=(
                repository_root.resolve()
            )
        )
    )

    resolver = PromotionTargetResolver(
        execution_repository=(
            execution_repository
        ),
        task_repository=task_repository,
        git_inspector=git_inspector,
        repository_root=repository_root,
        allowed_projects=(
            allowed_projects
            if allowed_projects is not None
            else {
                "puntuacion_padel": (
                    "puntuacion_padel"
                ),
            }
        ),
        test_target=".",
    )

    return (
        resolver,
        execution_repository,
        task_repository,
        git_inspector,
    )


def test_resolves_authorized_target(
    tmp_path: Path,
) -> None:
    repository_root = (
        tmp_path / "Agentes"
    )
    repository_root.mkdir()

    (
        resolver,
        execution_repository,
        task_repository,
        git_inspector,
    ) = create_resolver(
        repository_root
    )

    target = resolver.resolve(7)

    assert (
        target.repository_root
        == repository_root.resolve()
    )
    assert (
        target.target_project_name
        == "puntuacion_padel"
    )
    assert (
        target.target_subdirectory
        == "puntuacion_padel"
    )
    assert target.test_target == "."
    assert target.execution_id == 7

    execution_repository.get_by_id.assert_called_once_with(
        7
    )
    task_repository.get_by_id.assert_called_once_with(
        3
    )
    git_inspector.inspect.assert_called_once_with(
        repository_root=repository_root,
        require_clean=True,
    )


def test_rejects_missing_execution(
    tmp_path: Path,
) -> None:
    (
        resolver,
        execution_repository,
        _,
        git_inspector,
    ) = create_resolver(tmp_path)

    execution_repository.get_by_id.return_value = (
        None
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="No existe la ejecucion",
    ):
        resolver.resolve(7)

    git_inspector.inspect.assert_not_called()


def test_rejects_missing_target_project(
    tmp_path: Path,
) -> None:
    (
        resolver,
        _,
        _,
        git_inspector,
    ) = create_resolver(
        repository_root=tmp_path,
        target_project_name=None,
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="no identifica",
    ):
        resolver.resolve(7)

    git_inspector.inspect.assert_not_called()


def test_rejects_unlisted_project(
    tmp_path: Path,
) -> None:
    (
        resolver,
        _,
        _,
        git_inspector,
    ) = create_resolver(
        repository_root=tmp_path,
        target_project_name=(
            "proyecto_desconocido"
        ),
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="no esta autorizado",
    ):
        resolver.resolve(7)

    git_inspector.inspect.assert_not_called()


def test_rejects_unsafe_allowed_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="no es valido",
    ):
        create_resolver(
            repository_root=tmp_path,
            allowed_projects={
                "puntuacion_padel": (
                    "../fuera"
                ),
            },
        )


def test_rejects_repository_root_target(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="raiz completa",
    ):
        create_resolver(
            repository_root=tmp_path,
            allowed_projects={
                "puntuacion_padel": ".",
            },
        )


def test_reports_dirty_repository(
    tmp_path: Path,
) -> None:
    (
        resolver,
        _,
        _,
        git_inspector,
    ) = create_resolver(tmp_path)

    git_inspector.inspect.side_effect = (
        GitRepositoryInspectionError(
            "El repositorio objetivo contiene "
            "cambios sin confirmar"
        )
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="cambios sin confirmar",
    ):
        resolver.resolve(7)


def test_rejects_file_as_target(
    tmp_path: Path,
) -> None:
    repository_root = (
        tmp_path / "Agentes"
    )
    repository_root.mkdir()

    (
        repository_root
        / "puntuacion_padel"
    ).write_text(
        "no es un directorio",
        encoding="utf-8",
    )

    (
        resolver,
        _,
        _,
        _,
    ) = create_resolver(
        repository_root
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="no es un directorio",
    ):
        resolver.resolve(7)

def test_resolves_target_from_task_id(
    tmp_path: Path,
) -> None:
    repository_root = (
        tmp_path / "Agentes"
    )
    repository_root.mkdir()

    (
        resolver,
        execution_repository,
        _,
        _,
    ) = create_resolver(
        repository_root
    )

    execution_repository.get_by_task_id.return_value = (
        SimpleNamespace(
            id=7,
            task_id=3,
        )
    )

    target = resolver.resolve_task(3)

    assert target.execution_id == 7
    assert (
        target.target_subdirectory
        == "puntuacion_padel"
    )

    execution_repository.get_by_task_id.assert_called_once_with(
        3
    )
    execution_repository.get_by_id.assert_called_once_with(
        7
    )


def test_rejects_task_without_execution(
    tmp_path: Path,
) -> None:
    (
        resolver,
        execution_repository,
        _,
        git_inspector,
    ) = create_resolver(tmp_path)

    execution_repository.get_by_task_id.return_value = (
        None
    )

    with pytest.raises(
        PromotionTargetResolutionError,
        match="no tiene una ejecucion",
    ):
        resolver.resolve_task(3)

    execution_repository.get_by_id.assert_not_called()
    git_inspector.inspect.assert_not_called()