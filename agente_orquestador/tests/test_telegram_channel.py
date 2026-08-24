from types import SimpleNamespace

from app.channels.telegram import TelegramChannel
from app.context import (
    ContextBuilder,
    ContextDatabase,
    ContextQueryService,
    ContextSearchService,
    DocumentRepository,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
)
from app.models import (
    ChannelName,
    ContentType,
    OutgoingMessage,
)
from app.orchestrator import Orchestrator
from app.response_generation_service import (
    GeneratedAnswer,
)


class FakeResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
    ) -> GeneratedAnswer:
        return GeneratedAnswer(
            text="Respuesta simulada",
            model="modelo-de-prueba",
            elapsed_seconds=1.0,
            document_paths=(),
            message_ids=(),
            context_characters=0,
            context_truncated=False,
        )


def create_channel() -> TelegramChannel:
    database = ContextDatabase(
        ":memory:"
    ).connect()

    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    document_repository = DocumentRepository(
        database
    )
    message_repository = MessageRepository(
        database
    )

    context_builder = ContextBuilder(
        ContextSearchService(
            document_repository=(
                document_repository
            ),
            message_repository=(
                message_repository
            ),
        )
    )

    orchestrator = Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=message_repository,
        context_query_service=(
            ContextQueryService(database)
        ),
        context_builder=context_builder,
        response_generation_service=(
            FakeResponseGenerationService()
        ),
    )

    return TelegramChannel(
        token="token-de-prueba",
        allowed_user_id=123456,
        orchestrator=orchestrator,
    )


def test_authorizes_configured_user() -> None:
    channel = create_channel()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=123456
        )
    )

    assert channel.is_authorized(update)


def test_rejects_unconfigured_user() -> None:
    channel = create_channel()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=999999
        )
    )

    assert not channel.is_authorized(update)


def test_creates_incoming_from_telegram() -> None:
    channel = create_channel()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=123456,
            username="jose",
        ),
        effective_chat=SimpleNamespace(
            id=654321,
        ),
        message=SimpleNamespace(
            message_id=42,
            text="Hola, orquestador",
        ),
    )

    incoming = channel.create_incoming(
        update
    )

    assert incoming.channel == (
        ChannelName.TELEGRAM
    )
    assert incoming.content_type == (
        ContentType.TEXT
    )
    assert incoming.user_id == "123456"
    assert (
        incoming.conversation_id
        == "654321"
    )
    assert (
        incoming.text
        == "Hola, orquestador"
    )
    assert incoming.message_id == (
        "telegram:654321:42"
    )


def test_creates_command_from_telegram() -> None:
    channel = create_channel()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=123456,
            username="jose",
        ),
        effective_chat=SimpleNamespace(
            id=654321,
        ),
        message=SimpleNamespace(
            message_id=43,
            text="/contexto",
        ),
    )

    incoming = channel.create_incoming(
        update=update,
        content_type=ContentType.COMMAND,
    )

    assert incoming.content_type == (
        ContentType.COMMAND
    )
    assert incoming.text == "/contexto"

def test_formats_execution_time_in_minutes() -> None:
    outgoing = OutgoingMessage(
        channel=ChannelName.TELEGRAM,
        conversation_id="654321",
        content_type=ContentType.TEXT,
        correlation_id="mensaje-1",
        text="Respuesta generada",
        metadata={
            "elapsed_seconds": 70.8,
            "model": "qwen2.5-coder:3b",
        },
    )

    text = TelegramChannel.format_outgoing_text(
        outgoing
    )

    assert "Respuesta generada" in text
    assert "1,18 minutos" in text
    assert "qwen2.5-coder:3b" in text