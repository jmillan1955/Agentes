from pathlib import Path

import pytest

from app.execution.workspace import (
    WorkspacePolicy,
    WorkspaceViolationError,
)


def test_resolves_project_inside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"

    policy = WorkspacePolicy(
        allowed_root=root
    )

    result = policy.resolve(
        "proyecto_temporal"
    )

    assert result == (
        root / "proyecto_temporal"
    ).resolve()
    assert result.exists() is False


@pytest.mark.parametrize(
    "project_name",
    (
        "",
        "   ",
        "..",
        "../fuera",
        "carpeta/proyecto",
        "carpeta\\proyecto",
        "/ruta-absoluta",
        "proyecto con espacios",
    ),
)
def test_rejects_unsafe_project_name(
    tmp_path: Path,
    project_name: str,
) -> None:
    policy = WorkspacePolicy(
        allowed_root=tmp_path
    )

    with pytest.raises(
        WorkspaceViolationError
    ):
        policy.resolve(project_name)


def test_rejects_protected_path(
    tmp_path: Path,
) -> None:
    protected = (
        tmp_path / "agente_orquestador"
    )

    policy = WorkspacePolicy(
        allowed_root=tmp_path,
        protected_paths=(protected,),
    )

    with pytest.raises(
        WorkspaceViolationError,
        match="ruta protegida",
    ):
        policy.resolve(
            "agente_orquestador"
        )


def test_rejects_existing_file(
    tmp_path: Path,
) -> None:
    existing_file = (
        tmp_path / "proyecto_temporal"
    )
    existing_file.write_text(
        "contenido",
        encoding="utf-8",
    )

    policy = WorkspacePolicy(
        allowed_root=tmp_path
    )

    with pytest.raises(
        WorkspaceViolationError,
        match="no es un directorio",
    ):
        policy.resolve(
            "proyecto_temporal"
        )


def test_accepts_existing_directory(
    tmp_path: Path,
) -> None:
    existing_directory = (
        tmp_path / "proyecto_temporal"
    )
    existing_directory.mkdir()

    policy = WorkspacePolicy(
        allowed_root=tmp_path
    )

    assert policy.resolve(
        "proyecto_temporal"
    ) == existing_directory.resolve()