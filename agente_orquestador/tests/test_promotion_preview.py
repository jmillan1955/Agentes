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


def create_git_repository(
    path: Path,
) -> Path:
    path.mkdir()
    (path / ".git").mkdir()

    return path


def create_service() -> (
    PromotionPreviewService
):
    return PromotionPreviewService(
        workspace_packager=(
            WorkspacePackager()
        )
    )


def test_creates_preview_without_writing_target(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target = create_git_repository(
        tmp_path / "repository"
    )

    (workspace / "nuevo.py").write_text(
        "NUEVO = True\n",
        encoding="utf-8",
        newline="",
    )
    (workspace / "modificado.py").write_text(
        "VALOR = 2\n",
        encoding="utf-8",
        newline="",
    )
    (workspace / "igual.py").write_text(
        "IGUAL = True\n",
        encoding="utf-8",
        newline="",
    )

    (target / "modificado.py").write_text(
        "VALOR = 1\n",
        encoding="utf-8",
        newline="",
    )
    (target / "igual.py").write_text(
        "IGUAL = True\n",
        encoding="utf-8",
        newline="",
    )

    preview = create_service().create(
        workspace_path=workspace,
        target_repository_root=target,
    )

    assert tuple(
        change.relative_path
        for change in preview.changes
    ) == (
        "igual.py",
        "modificado.py",
        "nuevo.py",
    )

    assert tuple(
        change.change_type
        for change in preview.changes
    ) == (
        PromotionChangeType.UNCHANGED,
        PromotionChangeType.MODIFIED,
        PromotionChangeType.ADDED,
    )

    assert preview.added_count == 1
    assert preview.modified_count == 1
    assert preview.unchanged_count == 1
    assert preview.changed_count == 2
    assert len(preview.preview_hash) == 64

    modified = preview.changes[1]

    assert "-VALOR = 1" in (
        modified.diff_text
    )
    assert "+VALOR = 2" in (
        modified.diff_text
    )

    assert (
        target / "nuevo.py"
    ).exists() is False
    assert (
        target / "modificado.py"
    ).read_text(
        encoding="utf-8"
    ) == "VALOR = 1\n"


def test_ignores_target_only_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target = create_git_repository(
        tmp_path / "repository"
    )

    (workspace / "nuevo.py").write_text(
        "NUEVO = True\n",
        encoding="utf-8",
    )
    (target / "conservar.py").write_text(
        "CONSERVAR = True\n",
        encoding="utf-8",
    )

    preview = create_service().create(
        workspace_path=workspace,
        target_repository_root=target,
    )

    assert tuple(
        change.relative_path
        for change in preview.changes
    ) == ("nuevo.py",)

    assert (
        target / "conservar.py"
    ).exists()


def test_preview_hash_is_deterministic(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target = create_git_repository(
        tmp_path / "repository"
    )

    (workspace / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
        newline="",
    )

    service = create_service()

    first = service.create(
        workspace_path=workspace,
        target_repository_root=target,
    )
    second = service.create(
        workspace_path=workspace,
        target_repository_root=target,
    )

    assert (
        first.preview_hash
        == second.preview_hash
    )


def test_rejects_missing_git_repository(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target = tmp_path / "repository"
    target.mkdir()

    (workspace / "suma.py").write_text(
        "contenido",
        encoding="utf-8",
    )

    with pytest.raises(
        PromotionPreviewError,
        match="no es un repositorio Git",
    ):
        create_service().create(
            workspace_path=workspace,
            target_repository_root=target,
        )


@pytest.mark.parametrize(
    "workspace_inside_target",
    (
        True,
        False,
    ),
)
def test_rejects_nested_roots(
    tmp_path: Path,
    workspace_inside_target: bool,
) -> None:
    if workspace_inside_target:
        target = create_git_repository(
            tmp_path / "repository"
        )
        workspace = (
            target / "workspace"
        )
        workspace.mkdir()

    else:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = create_git_repository(
            workspace / "repository"
        )

    (workspace / "suma.py").write_text(
        "contenido",
        encoding="utf-8",
    )

    with pytest.raises(
        PromotionPreviewError,
        match="deben estar separados",
    ):
        create_service().create(
            workspace_path=workspace,
            target_repository_root=target,
        )


def test_rejects_non_utf8_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target = create_git_repository(
        tmp_path / "repository"
    )

    (workspace / "datos.txt").write_bytes(
        b"\xff\xfe"
    )

    with pytest.raises(
        PromotionPreviewError,
        match="UTF-8",
    ):
        create_service().create(
            workspace_path=workspace,
            target_repository_root=target,
        )