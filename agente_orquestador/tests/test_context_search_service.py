from hashlib import sha256

import pytest

from app.context import (
    ContextDatabase,
    ContextSearchService,
    DocumentRepository,
    ProjectRepository,
    MessageRepository,
    SessionRepository,
)

from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)

def save_document(
    repository: DocumentRepository,
    project_id: int,
    relative_path: str,
    title: str,
    content: str,
) -> None:
    repository.save(
        project_id=project_id,
        relative_path=relative_path,
        title=title,
        content=content,
        content_hash=sha256(
            content.encode("utf-8")
        ).hexdigest(),
    )


def create_service(
    database: ContextDatabase,
) -> tuple[
    int,
    ContextSearchService,
]:
    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    repository = DocumentRepository(
        database
    )

    return (
        project.id,
        ContextSearchService(
            document_repository=repository,
            message_repository=MessageRepository(
                database
            ),
        ),        
    )


def test_finds_document_by_title() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        repository = DocumentRepository(
            database
        )

        save_document(
            repository=repository,
            project_id=project_id,
            relative_path=(
                "docs/hitos/telegram.md"
            ),
            title="Integración con Telegram",
            content=(
                "El canal recibe mensajes "
                "del usuario."
            ),
        )

        result = service.search_documents(
            project_id=project_id,
            query=(
                "¿Cómo integramos Telegram?"
            ),
        )

        assert result.terms == (
            "integramos",
            "telegram",
        )
        assert len(result.documents) == 1
        assert (
            result.documents[0].title
            == "Integración con Telegram"
        )
        assert "telegram" in (
            result.documents[0]
            .matched_terms
        )


def test_orders_documents_by_relevance() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        repository = DocumentRepository(
            database
        )

        save_document(
            repository=repository,
            project_id=project_id,
            relative_path="docs/general.md",
            title="Arquitectura general",
            content=(
                "Telegram se utiliza "
                "como canal de entrada."
            ),
        )

        save_document(
            repository=repository,
            project_id=project_id,
            relative_path="docs/telegram.md",
            title="Telegram",
            content=(
                "Configuración completa "
                "del canal Telegram."
            ),
        )

        result = service.search_documents(
            project_id=project_id,
            query="Telegram",
        )

        assert len(result.documents) == 2
        assert (
            result.documents[0].title
            == "Telegram"
        )
        assert (
            result.documents[0].score
            > result.documents[1].score
        )


def test_returns_empty_result_without_matches() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        result = service.search_documents(
            project_id=project_id,
            query="Aerotermia",
        )

        assert result.documents == ()


def test_rejects_invalid_limit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        with pytest.raises(
            ValueError,
            match="limit debe ser mayor que cero",
        ):
            service.search_documents(
                project_id=project_id,
                query="Telegram",
                limit=0,
            )

def test_finds_related_messages() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        repository = MessageRepository(
            database
        )

        telegram_message = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario",
            conversation_id="conversacion",
            content_type=ContentType.TEXT,
            text=(
                "Integraremos el canal Telegram "
                "en el orquestador"
            ),
        )

        unrelated_message = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario",
            conversation_id="conversacion",
            content_type=ContentType.TEXT,
            text=(
                "Mañana prepararemos una "
                "receta de cocina"
            ),
        )

        repository.save_incoming(
            session.id,
            telegram_message,
        )
        repository.save_incoming(
            session.id,
            unrelated_message,
        )

        result = service.search_messages(
            project_id=project_id,
            query="Integración de Telegram",
        )

        assert len(result.messages) == 1
        assert (
            result.messages[0].message_id
            == telegram_message.message_id
        )
        assert (
            result.messages[0].direction
            == "incoming"
        )
        assert "telegram" in (
            result.messages[0]
            .matched_terms
        )


def test_excludes_current_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        repository = MessageRepository(
            database
        )

        current_message = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario",
            conversation_id="conversacion",
            content_type=ContentType.TEXT,
            text="Consulta sobre Telegram",
        )

        repository.save_incoming(
            session.id,
            current_message,
        )

        result = service.search_messages(
            project_id=project_id,
            query="Telegram",
            exclude_message_id=(
                current_message.message_id
            ),
        )

        assert result.messages == ()

def test_excludes_outgoing_messages_by_default() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, service = create_service(
            database
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project_id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        repository = MessageRepository(
            database
        )

        outgoing = OutgoingMessage(
            channel=ChannelName.TELEGRAM,
            conversation_id="conversacion",
            content_type=ContentType.TEXT,
            correlation_id="mensaje-entrada-1",
            text=(
                "Resumen automático del "
                "contexto del orquestador"
            ),
        )
        
        repository.save_outgoing(
            session.id,
            outgoing,
        )

        default_result = (
            service.search_messages(
                project_id=project_id,
                query="contexto orquestador",
            )
        )

        complete_result = (
            service.search_messages(
                project_id=project_id,
                query="contexto orquestador",
                include_outgoing=True,
            )
        )

        assert default_result.messages == ()
        assert len(
            complete_result.messages
        ) == 1