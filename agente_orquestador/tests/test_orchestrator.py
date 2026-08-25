from hashlib import sha256

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
    Attachment,
    ChannelName,
    ContentType,
    IncomingMessage,
)
from app.orchestrator import Orchestrator
from app.providers import (
    LanguageProviderError,
)
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
            text=(
                "Respuesta generada para: "
                f"{query}"
            ),
            model="modelo-de-prueba",
            elapsed_seconds=1.5,
            document_paths=(),
            message_ids=(),
            context_characters=100,
            context_truncated=False,
        )


class FailingResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
    ) -> GeneratedAnswer:
        raise LanguageProviderError(
            "Proveedor no disponible"
        )


class UnexpectedResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
    ):
        raise AssertionError(
            "Una tarea no debe enviarse "
            "al proveedor de lenguaje"
        )

def create_orchestrator(
    database: ContextDatabase,
    context_query_service: (
        ContextQueryService | None
    ) = None,
    response_generation_service=None,
) -> Orchestrator:
    if context_query_service is None:
        context_query_service = (
            ContextQueryService(database)
        )

    if response_generation_service is None:
        response_generation_service = (
            FakeResponseGenerationService()
        )

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

    return Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=message_repository,
        context_query_service=(
            context_query_service
        ),
        context_builder=context_builder,
        response_generation_service=(
            response_generation_service
        ),
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
        assert (
            outgoing.metadata["model"]
            == "modelo-de-prueba"
        )
        assert (
            outgoing.metadata[
                "elapsed_seconds"
            ]
            == 1.5
        )


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
        assert (
            "Mensajes registrados:"
            in outgoing.text
        )


def test_searches_context_for_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project = ProjectRepository(
            database
        ).save(
            name="Proyecto documental",
            root_path="ruta-documental",
        )

        content = (
            "Telegram es el canal de entrada "
            "del Agente Orquestador."
        )

        document_repository = (
            DocumentRepository(database)
        )

        document_repository.save(
            project_id=project.id,
            relative_path="docs/telegram.md",
            title="Integración Telegram",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        message_repository = (
            MessageRepository(database)
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
            session_repository=(
                SessionRepository(database)
            ),
            message_repository=(
                message_repository
            ),
            context_query_service=(
                ContextQueryService(database)
            ),
            context_builder=context_builder,
            response_generation_service=(
                FakeResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/buscar Telegram",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "CONTEXTO RECUPERADO"
            in outgoing.text
        )
        assert (
            "Integración Telegram"
            in outgoing.text
        )


def test_requires_search_query() -> None:
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
            text="/buscar",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar qué quieres buscar"
            in outgoing.text
        )


def test_controls_language_provider_error() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            response_generation_service=(
                FailingResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "¿Cuál es la capital "
                "de Portugal?"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "No se ha podido generar "
            "la respuesta"
            in outgoing.text
        )
        assert (
            "Proveedor no disponible"
            in outgoing.text
        )
        assert (
            outgoing.metadata["error"]
            == "LanguageProviderError"
        )
        assert (
            incoming.message_id
            not in outgoing.text
        )

def test_adds_routing_decision_to_metadata() -> None:
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
            text=(
                "Añade un canal de correo "
                "al Agente Orquestador"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert (
            outgoing.metadata["routing_kind"]
            == "task"
        )
        assert (
            outgoing.metadata[
                "routing_confidence"
            ]
            == 0.90
        )
        assert (
            outgoing.metadata[
                "routing_project"
            ]
            == "Agente Orquestador"
        )
        assert not outgoing.metadata[
            "routing_requires_clarification"
        ]

def test_classifies_request_from_command() -> None:
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
            text=(
                "/clasificar Añade un canal "
                "de correo"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "CLASIFICACIÓN DE LA PETICIÓN"
            in outgoing.text
        )
        assert "Tipo: task" in outgoing.text
        assert "Confianza: 90%" in outgoing.text
        assert (
            "Necesita aclaración: No"
            in outgoing.text
        )

def test_requires_request_to_classify() -> None:
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
            text="/clasificar",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar una petición"
            in outgoing.text
        )

def test_routes_task_without_calling_language_provider() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            response_generation_service=(
                UnexpectedResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "Crea el proyecto "
                "agente_audioText"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "PETICIÓN IDENTIFICADA COMO TAREA"
            in outgoing.text
        )
        assert (
            "No se ha ejecutado ningún cambio"
            in outgoing.text
        )
        assert (
            outgoing.metadata["routing_kind"]
            == "task"
        )
        assert (
            outgoing.metadata["route"]
            == "task_handler"
        )
        assert (
            outgoing.metadata["task_status"]
            == "pending_planning"
        )
        assert "model" not in outgoing.metadata