from pathlib import Path
import subprocess

from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.promotion_application import (
    PromotionApplicationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)


def run_git(
    repository: Path,
    *arguments: str,
) -> None:
    subprocess.run(
        (
            "git",
            "-C",
            str(repository),
            *arguments,
        ),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def create_repository(
    repository: Path,
) -> None:
    repository.mkdir()

    run_git(
        repository,
        "init",
        "-b",
        "master",
    )
    run_git(
        repository,
        "config",
        "user.name",
        "Prueba",
    )
    run_git(
        repository,
        "config",
        "user.email",
        "prueba@example.com",
    )

    readme = repository / "README.md"

    readme.write_text(
        "# Repositorio temporal\n",
        encoding="utf-8",
    )

    run_git(repository, "add", "README.md")
    run_git(
        repository,
        "commit",
        "-m",
        "Commit inicial",
    )


def create_services(
) -> tuple[
    PromotionPreviewService,
    PromotionApplicationService,
]:
    preview_service = (
        PromotionPreviewService(
            workspace_packager=(
                WorkspacePackager()
            )
        )
    )

    application_service = (
        PromotionApplicationService(
            preview_service=preview_service,
            git_inspector=(
                GitRepositoryInspector()
            ),
        )
    )

    return (
        preview_service,
        application_service,
    )


def test_applies_inside_project_subdirectory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    repository = tmp_path / "repository"

    workspace.mkdir()
    create_repository(repository)

    (workspace / "suma.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    (
        preview_service,
        application_service,
    ) = create_services()

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
        target_subdirectory=(
            "puntuacion_padel"
        ),
    )

    result = application_service.apply(
        preview=preview,
        confirmed_preview_hash=(
            preview.preview_hash
        ),
    )

    target = (
        repository
        / "puntuacion_padel"
        / "suma.py"
    )

    assert target.is_file()
    assert (
        target.read_text(
            encoding="utf-8"
        )
        == (
            "def sumar(a, b):\n"
            "    return a + b\n"
        )
    )

    assert not (
        repository / "suma.py"
    ).exists()

    assert result.written_paths == (
        "puntuacion_padel/suma.py",
    )

    application_service.rollback(result)

    assert not target.exists()
    assert not (
        repository / "puntuacion_padel"
    ).exists()

    GitRepositoryInspector().inspect(
        repository
    )