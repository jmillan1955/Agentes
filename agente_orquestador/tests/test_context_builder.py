from hashlib import sha256

import pytest

from app.context import (
    ContextBuilder,
    ContextDatabase,
    ContextSearchService,
    DocumentRepository,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
)
from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
)


def create_builder(
    database: ContextDatabase,
) -> tuple[
    int,
    ContextBuilder,
    MessageRepository,
]:
    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    documents = DocumentRepository(
        database
    )
    messages = MessageRepository(
        database
    )

    search_service = ContextSearchService(
        document_repository=documents,
        message_repository=messages,
    )

    return (
        project.id,
        ContextBuilder(search_service),
        messages,
    )


def test_builds_context_from_documents() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, builder, _ = (
            create_builder(database)
        )

        content = (
            "# Telegram\n\n"
            "Telegram es el canal de entrada "
            "predeterminado del orquestador."
        )

        DocumentRepository(database).save(
            project_id=project_id,
            relative_path=(
                "docs/telegram.md"
            ),
            title="Canal Telegram",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        context = builder.build(
            project_id=project_id,
            query=(
                "¿Cómo funciona Telegram?"
            ),
        )

        assert "DOCUMENTOS RELEVANTES" in (
            context.text
        )
        assert "Canal Telegram" in context.text
        assert "docs/telegram.md" in (
            context.document_paths
        )
        assert context.truncated is False


def test_combines_documents_and_messages() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        (
            project_id,
            builder,
            messages,
        ) = create_builder(database)

        content = (
            "El contexto se almacena "
            "en una base de datos SQLite."
        )

        DocumentRepository(database).save(
            project_id=project_id,
            relative_path="docs/contexto.md",
            title="Almacén de contexto",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        previous_message = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario",
            conversation_id="conversacion",
            content_type=ContentType.TEXT,
            text=(
                "El contexto debe conservar "
                "los documentos del proyecto"
            ),
        )

        messages.save_incoming(
            session.id,
            previous_message,
        )

        context = builder.build(
            project_id=project_id,
            query=(
                "¿Dónde guardamos el contexto?"
            ),
        )

        assert "DOCUMENTOS RELEVANTES" in (
            context.text
        )
        assert (
            "CONVERSACIONES RELEVANTES"
            in context.text
        )
        assert (
            previous_message.message_id
            in context.message_ids
        )


def test_respects_character_limit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, builder, _ = (
            create_builder(database)
        )

        content = (
            "Telegram " * 200
        )

        DocumentRepository(database).save(
            project_id=project_id,
            relative_path="docs/telegram.md",
            title="Telegram",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        context = builder.build(
            project_id=project_id,
            query="Telegram",
            maximum_characters=150,
        )

        assert context.truncated is True
        assert context.total_characters <= 150
        assert context.text.endswith("...")


def test_rejects_too_small_limit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, builder, _ = (
            create_builder(database)
        )

        with pytest.raises(
            ValueError,
            match=(
                "maximum_characters debe ser "
                "al menos 100"
            ),
        ):
            builder.build(
                project_id=project_id,
                query="Telegram",
                maximum_characters=99,
            )