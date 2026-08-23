from app.context import (
    ContextDatabase,
    GitCommitRepository,
    ProjectRepository,
)


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


def test_saves_and_recovers_commit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = GitCommitRepository(
            database
        )

        saved = repository.save(
            commit_hash="abc123",
            project_id=project_id,
            parent_hash="anterior123",
            author_name="José Millán",
            authored_at=(
                "2026-08-23T10:00:00+02:00"
            ),
            subject="Crear el orquestador",
            body="Primer commit del proyecto.",
        )

        recovered = repository.get_by_hash(
            "abc123"
        )

        assert recovered == saved
        assert recovered is not None
        assert recovered.project_id == project_id
        assert (
            recovered.subject
            == "Crear el orquestador"
        )


def test_updates_existing_commit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = GitCommitRepository(
            database
        )

        first = repository.save(
            commit_hash="abc123",
            project_id=project_id,
            authored_at=(
                "2026-08-23T10:00:00+02:00"
            ),
            subject="Mensaje inicial",
        )

        second = repository.save(
            commit_hash="abc123",
            project_id=project_id,
            authored_at=(
                "2026-08-23T10:00:00+02:00"
            ),
            subject="Mensaje actualizado",
        )

        assert (
            second.commit_hash
            == first.commit_hash
        )
        assert (
            second.subject
            == "Mensaje actualizado"
        )


def test_lists_commits_newest_first() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = GitCommitRepository(
            database
        )

        repository.save(
            commit_hash="antiguo",
            project_id=project_id,
            authored_at=(
                "2026-08-22T10:00:00+02:00"
            ),
            subject="Commit antiguo",
        )

        repository.save(
            commit_hash="nuevo",
            project_id=project_id,
            authored_at=(
                "2026-08-23T10:00:00+02:00"
            ),
            subject="Commit nuevo",
        )

        commits = repository.list_by_project(
            project_id
        )

        assert [
            commit.commit_hash
            for commit in commits
        ] == [
            "nuevo",
            "antiguo",
        ]


def test_returns_none_for_unknown_commit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = GitCommitRepository(
            database
        )

        result = repository.get_by_hash(
            "inexistente"
        )

        assert result is None