import subprocess
from pathlib import Path

import pytest

from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.promotion_application import (
    PromotionApplicationError,
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
) -> str:
    result = subprocess.run(
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
        errors="replace",
    )

    return result.stdout.strip()


def create_repository(
    path: Path,
) -> Path:
    path.mkdir()

    run_git(path, "init", "-b", "main")
    run_git(
        path,
        "config",
        "user.name",
        "Usuario de prueba",
    )
    run_git(
        path,
        "config",
        "user.email",
        "prueba@example.com",
    )

    (path / "modificado.py").write_text(
        "VALOR = 1\n",
        encoding="utf-8",
        newline="",
    )
    (path / "igual.py").write_text(
        "IGUAL = True\n",
        encoding="utf-8",
        newline="",
    )

    run_git(path, "add", ".")
    run_git(
        path,
        "commit",
        "-m",
        "Commit inicial",
    )

    return path


def create_workspace(
    path: Path,
) -> Path:
    path.mkdir()

    (path / "modificado.py").write_text(
        "VALOR = 2\n",
        encoding="utf-8",
        newline="",
    )
    (path / "igual.py").write_text(
        "IGUAL = True\n",
        encoding="utf-8",
        newline="",
    )

    tests = path / "tests"
    tests.mkdir()

    (tests / "test_nuevo.py").write_text(
        "def test_nuevo():\n"
        "    assert True\n",
        encoding="utf-8",
        newline="",
    )

    return path


def create_services() -> tuple[
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


def test_applies_confirmed_preview(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository = create_repository(
        tmp_path / "repository"
    )

    preview_service, application_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )
    original_head = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    result = application_service.apply(
        preview=preview,
        confirmed_preview_hash=(
            preview.preview_hash
        ),
    )

    assert result.written_paths == (
        "modificado.py",
        "tests/test_nuevo.py",
    )
    assert result.added_count == 1
    assert result.modified_count == 1
    assert result.branch_name == "main"
    assert result.head_commit == original_head

    assert (
        repository / "modificado.py"
    ).read_text(
        encoding="utf-8"
    ) == "VALOR = 2\n"

    assert (
        repository
        / "tests"
        / "test_nuevo.py"
    ).is_file()

    assert (
        repository / "igual.py"
    ).read_text(
        encoding="utf-8"
    ) == "IGUAL = True\n"

    assert run_git(
        repository,
        "rev-parse",
        "HEAD",
    ) == original_head

    assert run_git(
        repository,
        "status",
        "--porcelain",
    )


def test_rejects_unconfirmed_hash(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository = create_repository(
        tmp_path / "repository"
    )

    preview_service, application_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    with pytest.raises(
        PromotionApplicationError,
        match="hash confirmado",
    ):
        application_service.apply(
            preview=preview,
            confirmed_preview_hash=(
                "0" * 64
            ),
        )

    assert (
        repository / "modificado.py"
    ).read_text(
        encoding="utf-8"
    ) == "VALOR = 1\n"


def test_rejects_changed_workspace(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository = create_repository(
        tmp_path / "repository"
    )

    preview_service, application_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    (workspace / "modificado.py").write_text(
        "VALOR = 3\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        PromotionApplicationError,
        match="han cambiado",
    ):
        application_service.apply(
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )

    assert (
        repository / "modificado.py"
    ).read_text(
        encoding="utf-8"
    ) == "VALOR = 1\n"


def test_rejects_dirty_repository(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository = create_repository(
        tmp_path / "repository"
    )

    preview_service, application_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    (repository / "externo.txt").write_text(
        "cambio externo\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PromotionApplicationError,
        match="cambios sin confirmar",
    ):
        application_service.apply(
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )


def test_rejects_preview_without_changes(
    tmp_path: Path,
) -> None:
    repository = create_repository(
        tmp_path / "repository"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    for name in (
        "modificado.py",
        "igual.py",
    ):
        (workspace / name).write_bytes(
            (repository / name).read_bytes()
        )

    preview_service, application_service = (
        create_services()
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )

    with pytest.raises(
        PromotionApplicationError,
        match="no contiene cambios",
    ):
        application_service.apply(
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )


class FailingApplicationService(
    PromotionApplicationService
):
    def __init__(
        self,
        preview_service: PromotionPreviewService,
        git_inspector: GitRepositoryInspector,
    ) -> None:
        super().__init__(
            preview_service=preview_service,
            git_inspector=git_inspector,
        )
        self._write_count = 0

    def _write_atomic(
        self,
        target: Path,
        content: bytes,
    ) -> None:
        self._write_count += 1

        if self._write_count == 2:
            raise OSError(
                "Fallo simulado"
            )

        super()._write_atomic(
            target=target,
            content=content,
        )


def test_rolls_back_intermediate_failure(
    tmp_path: Path,
) -> None:
    workspace = create_workspace(
        tmp_path / "workspace"
    )
    repository = create_repository(
        tmp_path / "repository"
    )

    preview_service = (
        PromotionPreviewService(
            workspace_packager=(
                WorkspacePackager()
            )
        )
    )
    application_service = (
        FailingApplicationService(
            preview_service=preview_service,
            git_inspector=(
                GitRepositoryInspector()
            ),
        )
    )

    preview = preview_service.create(
        workspace_path=workspace,
        target_repository_root=repository,
    )
    original_status = run_git(
        repository,
        "status",
        "--porcelain",
    )

    with pytest.raises(
        PromotionApplicationError,
        match="restauro",
    ):
        application_service.apply(
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )

    assert (
        repository / "modificado.py"
    ).read_text(
        encoding="utf-8"
    ) == "VALOR = 1\n"

    assert (
        repository
        / "tests"
        / "test_nuevo.py"
    ).exists() is False

    assert run_git(
        repository,
        "status",
        "--porcelain",
    ) == original_status