from hashlib import sha256

from app.context import (
    ContextDatabase,
    DocumentRepository,
    ProjectRepository,
)


def calculate_hash(content: str) -> str:
    return sha256(
        content.encode("utf-8")
    ).hexdigest()


def create_project(
    database: ContextDatabase,
) -> int:
    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    return project.id


def test_saves_document() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = DocumentRepository(
            database
        )

        content = "# Arquitectura\n\nContenido."

        saved = repository.save(
            project_id=project_id,
            relative_path=(
                "docs/arquitectura.md"
            ),
            title="Arquitectura",
            content=content,
            content_hash=calculate_hash(content),
        )

        assert saved.project_id == project_id
        assert (
            saved.relative_path
            == "docs/arquitectura.md"
        )
        assert saved.title == "Arquitectura"
        assert saved.content == content


def test_updates_changed_document() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = DocumentRepository(
            database
        )

        first_content = "# Documento\n\nVersión 1"
        second_content = "# Documento\n\nVersión 2"

        first = repository.save(
            project_id=project_id,
            relative_path="docs/documento.md",
            content=first_content,
            content_hash=calculate_hash(
                first_content
            ),
        )

        second = repository.save(
            project_id=project_id,
            relative_path="docs/documento.md",
            content=second_content,
            content_hash=calculate_hash(
                second_content
            ),
        )

        assert second.id == first.id
        assert second.content == second_content
        assert (
            second.content_hash
            != first.content_hash
        )


def test_does_not_rewrite_unchanged_document() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = DocumentRepository(
            database
        )

        content = "# Documento sin cambios"
        content_hash = calculate_hash(content)

        first = repository.save(
            project_id=project_id,
            relative_path="docs/documento.md",
            content=content,
            content_hash=content_hash,
        )

        second = repository.save(
            project_id=project_id,
            relative_path="docs/documento.md",
            content=content,
            content_hash=content_hash,
        )

        assert second == first


def test_lists_documents_by_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = DocumentRepository(
            database
        )

        for path in [
            "docs/segundo.md",
            "docs/primero.md",
        ]:
            repository.save(
                project_id=project_id,
                relative_path=path,
                content=path,
                content_hash=calculate_hash(path),
            )

        documents = repository.list_by_project(
            project_id
        )

        assert [
            document.relative_path
            for document in documents
        ] == [
            "docs/primero.md",
            "docs/segundo.md",
        ]