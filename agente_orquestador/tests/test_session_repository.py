from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
)


def create_project(
    database: ContextDatabase,
) -> int:
    repository = ProjectRepository(
        database
    )

    project = repository.save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    return project.id


def test_creates_active_session() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = SessionRepository(
            database
        )

        session = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        assert session.project_id == project_id
        assert session.channel == "telegram"
        assert session.user_id == "123456"
        assert session.status == "active"
        assert session.ended_at is None


def test_reuses_existing_active_session() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = SessionRepository(
            database
        )

        first = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        second = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        assert second.id == first.id
        assert len(repository.list_active()) == 1


def test_closes_session_and_creates_another() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = SessionRepository(
            database
        )

        first = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        closed = repository.close(first.id)

        assert closed is not None
        assert closed.status == "closed"
        assert closed.ended_at is not None

        second = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        assert second.id != first.id
        assert second.status == "active"


def test_lists_only_active_sessions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)
        repository = SessionRepository(
            database
        )

        first = repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario-1",
            conversation_id="chat-1",
        )

        repository.get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario-2",
            conversation_id="chat-2",
        )

        repository.close(first.id)

        active = repository.list_active()

        assert len(active) == 1
        assert active[0].user_id == "usuario-2"