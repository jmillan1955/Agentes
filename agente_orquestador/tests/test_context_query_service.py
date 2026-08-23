from hashlib import sha256

import pytest

from app.context import (
    ContextDatabase,
    ContextQueryService,
    DocumentRepository,
    GitCommitRepository,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
)
from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
    OutgoingMessage,
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


def test_returns_empty_project_summary() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)

        summary = ContextQueryService(
            database
        ).get_summary(project_id)

        assert (
            summary.project_name
            == "Agente Orquestador"
        )
        assert summary.total_sessions == 0
        assert summary.active_sessions == 0
        assert summary.total_messages == 0
        assert summary.total_documents == 0
        assert summary.total_commits == 0
        assert summary.recent_documents == ()
        assert summary.recent_commits == ()


def test_returns_complete_context_summary() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id = create_project(database)

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="654321",
            content_type=ContentType.TEXT,
            text="Consulta de contexto",
        )

        outgoing = OutgoingMessage(
            channel=ChannelName.TELEGRAM,
            conversation_id="654321",
            content_type=ContentType.TEXT,
            correlation_id=incoming.message_id,
            text="Respuesta de contexto",
        )

        messages = MessageRepository(database)

        messages.save_incoming(
            session.id,
            incoming,
        )
        messages.save_outgoing(
            session.id,
            outgoing,
        )

        content = "# Hito 1"

        DocumentRepository(database).save(
            project_id=project_id,
            relative_path="docs/hito_1.md",
            title="Hito 1",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        GitCommitRepository(database).save(
            commit_hash="abc123",
            project_id=project_id,
            authored_at=(
                "2026-08-23T10:00:00+02:00"
            ),
            subject="Crear contexto",
        )

        summary = ContextQueryService(
            database
        ).get_summary(project_id)

        assert summary.total_sessions == 1
        assert summary.active_sessions == 1
        assert summary.total_messages == 2
        assert summary.total_documents == 1
        assert summary.total_commits == 1

        assert (
            summary.recent_documents[0].title
            == "Hito 1"
        )

        assert (
            summary.recent_commits[0].subject
            == "Crear contexto"
        )


def test_rejects_unknown_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        service = ContextQueryService(
            database
        )

        with pytest.raises(
            ValueError,
            match="No existe el proyecto",
        ):
            service.get_summary(
                project_id=999
            )