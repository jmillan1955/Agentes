from pathlib import Path

from app.context import (
    ContextDatabase,
    DocumentRepository,
    DocumentSynchronizer,
    ProjectRepository,
)


def create_components(
    tmp_path: Path,
) -> tuple[
    ContextDatabase,
    DocumentRepository,
    DocumentSynchronizer,
    int,
]:
    project_root = tmp_path / "project"
    documents_root = project_root / "docs"

    documents_root.mkdir(
        parents=True
    )

    database = ContextDatabase(
        ":memory:"
    ).connect()

    project = ProjectRepository(
        database
    ).save(
        name="Proyecto de prueba",
        root_path=str(project_root),
    )

    repository = DocumentRepository(
        database
    )

    synchronizer = DocumentSynchronizer(
        repository=repository,
        project_id=project.id,
        project_root=project_root,
    )

    return (
        database,
        repository,
        synchronizer,
        project.id,
    )


def test_imports_markdown_documents(
    tmp_path: Path,
) -> None:
    (
        database,
        repository,
        synchronizer,
        project_id,
    ) = create_components(tmp_path)

    try:
        document = (
            tmp_path
            / "project"
            / "docs"
            / "arquitectura.md"
        )

        document.write_text(
            "# Arquitectura\n\nContenido.",
            encoding="utf-8",
        )

        result = synchronizer.synchronize()

        assert result.scanned == 1
        assert result.created == 1
        assert result.updated == 0

        stored = repository.get_by_path(
            project_id=project_id,
            relative_path=(
                "docs/arquitectura.md"
            ),
        )

        assert stored is not None
        assert stored.title == "Arquitectura"
        assert stored.content == (
            "# Arquitectura\n\nContenido."
        )

    finally:
        database.close()


def test_detects_unchanged_document(
    tmp_path: Path,
) -> None:
    (
        database,
        _,
        synchronizer,
        _,
    ) = create_components(tmp_path)

    try:
        document = (
            tmp_path
            / "project"
            / "docs"
            / "documento.md"
        )

        document.write_text(
            "# Documento",
            encoding="utf-8",
        )

        first = synchronizer.synchronize()
        second = synchronizer.synchronize()

        assert first.created == 1
        assert second.created == 0
        assert second.updated == 0
        assert second.unchanged == 1

    finally:
        database.close()


def test_updates_changed_document(
    tmp_path: Path,
) -> None:
    (
        database,
        repository,
        synchronizer,
        project_id,
    ) = create_components(tmp_path)

    try:
        document = (
            tmp_path
            / "project"
            / "docs"
            / "documento.md"
        )

        document.write_text(
            "# Documento\n\nVersión 1",
            encoding="utf-8",
        )

        synchronizer.synchronize()

        document.write_text(
            "# Documento\n\nVersión 2",
            encoding="utf-8",
        )

        result = synchronizer.synchronize()

        assert result.updated == 1

        stored = repository.get_by_path(
            project_id=project_id,
            relative_path="docs/documento.md",
        )

        assert stored is not None
        assert "Versión 2" in stored.content

    finally:
        database.close()


def test_deletes_missing_document(
    tmp_path: Path,
) -> None:
    (
        database,
        repository,
        synchronizer,
        project_id,
    ) = create_components(tmp_path)

    try:
        document = (
            tmp_path
            / "project"
            / "docs"
            / "temporal.md"
        )

        document.write_text(
            "# Temporal",
            encoding="utf-8",
        )

        synchronizer.synchronize()
        document.unlink()

        result = synchronizer.synchronize()

        assert result.deleted == 1
        assert repository.get_by_path(
            project_id=project_id,
            relative_path="docs/temporal.md",
        ) is None

    finally:
        database.close()