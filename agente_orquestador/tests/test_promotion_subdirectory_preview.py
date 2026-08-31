from pathlib import Path

import pytest

from app.execution.promotion_models import (
    PromotionChangeType,
)
from app.execution.promotion_preview import (
    PromotionPreviewError,
    PromotionPreviewService,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)


def create_service(
) -> PromotionPreviewService:
    return PromotionPreviewService(
        workspace_packager=(
            WorkspacePackager()
        )
    )


def create_roots(
    tmp_path: Path,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    repository = tmp_path / "repository"

    workspace.mkdir()
    repository.mkdir()
    (repository / ".git").mkdir()

    return workspace, repository


def test_targets_project_subdirectory(
    tmp_path: Path,
) -> None:
    workspace, repository = (
        create_roots(tmp_path)
    )

    (workspace / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    project_directory = (
        repository / "puntuacion_padel"
    )
    project_directory.mkdir()

    (project_directory / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return 0\n",
        encoding="utf-8",
    )

    preview = create_service().create(
        workspace_path=workspace,
        target_repository_root=repository,
        target_subdirectory=(
            "puntuacion_padel"
        ),
    )

    assert (
        preview.target_subdirectory
        == "puntuacion_padel"
    )
    assert len(preview.changes) == 1

    change = preview.changes[0]

    assert (
        change.relative_path
        == "puntuacion_padel/suma.py"
    )
    assert (
        change.change_type
        == PromotionChangeType.MODIFIED
    )
    assert (
        "a/puntuacion_padel/suma.py"
        in change.diff_text
    )
    assert (
        "b/puntuacion_padel/suma.py"
        in change.diff_text
    )


def test_does_not_compare_with_root_file(
    tmp_path: Path,
) -> None:
    workspace, repository = (
        create_roots(tmp_path)
    )

    content = "valor = 1\n"

    (workspace / "modulo.py").write_text(
        content,
        encoding="utf-8",
    )
    (repository / "modulo.py").write_text(
        content,
        encoding="utf-8",
    )

    preview = create_service().create(
        workspace_path=workspace,
        target_repository_root=repository,
        target_subdirectory=(
            "puntuacion_padel"
        ),
    )

    assert (
        preview.changes[0].relative_path
        == "puntuacion_padel/modulo.py"
    )
    assert (
        preview.changes[0].change_type
        == PromotionChangeType.ADDED
    )


def test_preserves_root_compatibility(
    tmp_path: Path,
) -> None:
    workspace, repository = (
        create_roots(tmp_path)
    )

    (workspace / "modulo.py").write_text(
        "valor = 1\n",
        encoding="utf-8",
    )

    preview = create_service().create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    assert preview.target_subdirectory == "."
    assert (
        preview.changes[0].relative_path
        == "modulo.py"
    )


@pytest.mark.parametrize(
    "target_subdirectory",
    (
        "",
        "../fuera",
        "/ruta/absoluta",
        r"C:\ruta\absoluta",
    ),
)
def test_rejects_unsafe_subdirectory(
    tmp_path: Path,
    target_subdirectory: str,
) -> None:
    workspace, repository = (
        create_roots(tmp_path)
    )

    (workspace / "modulo.py").write_text(
        "valor = 1\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PromotionPreviewError
    ):
        create_service().create(
            workspace_path=workspace,
            target_repository_root=(
                repository
            ),
            target_subdirectory=(
                target_subdirectory
            ),
        )