from app.context import (
    ContextDatabase,
    ContextQueryService,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
)
from app.models import (
    Attachment,
    ChannelName,
    ContentType,
    IncomingMessage,
)
from app.orchestrator import Orchestrator


def create_orchestrator(
    database: ContextDatabase,
    context_query_service: ContextQueryService | None = None,
) -> Orchestrator:
    if context_query_service is None:
        context_query_service = ContextQueryService(
            database
        )

    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    return Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=MessageRepository(
            database
        ),
        context_query_service=context_query_service,
    )


def test_processes_text_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Hola, agente.",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.channel == incoming.channel
        assert (
            outgoing.conversation_id
            == incoming.conversation_id
        )
        assert (
            outgoing.correlation_id
            == incoming.message_id
        )
        assert outgoing.text is not None
        assert "Hola, agente." in outgoing.text


def test_persists_input_and_output() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Mensaje persistente.",
        )

        outgoing = orchestrator.process(
            incoming
        )

        session = SessionRepository(
            database
        ).list_active()[0]

        messages = MessageRepository(
            database
        ).list_by_session(
            session.id
        )

        assert len(messages) == 2

        assert messages[0].direction == "incoming"
        assert (
            messages[0].text
            == "Mensaje persistente."
        )

        assert messages[1].direction == "outgoing"
        assert (
            messages[1].correlation_id
            == incoming.message_id
        )
        assert messages[1].text == outgoing.text


def test_reuses_session_for_same_conversation() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        first = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Primer mensaje.",
        )

        second = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Segundo mensaje.",
        )

        orchestrator.process(first)
        orchestrator.process(second)

        sessions = SessionRepository(
            database
        ).list_active()

        assert len(sessions) == 1

        messages = MessageRepository(
            database
        ).list_by_session(
            sessions[0].id
        )

        assert len(messages) == 4


def test_reports_unsupported_content_type() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        attachment = Attachment(
            attachment_id="documento-1",
            content_type=ContentType.DOCUMENT,
            filename="prueba.txt",
            mime_type="text/plain",
            size_bytes=100,
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.DOCUMENT,
            attachments=(attachment,),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert "document" in outgoing.text
        assert (
            "solamente proceso texto"
            in outgoing.text
        )

def test_returns_context_for_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/contexto",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Contexto del Agente Orquestador"
            in outgoing.text
        )
        assert (
            "Proyecto: Agente Orquestador"
            in outgoing.text
        )
        assert "Sesiones:" in outgoing.text
        assert "Mensajes registrados:" in outgoing.text    