import pytest
from app.context import (
    ContextDatabase,
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


def create_session(
    database: ContextDatabase,
) -> int:
    project_repository = ProjectRepository(
        database
    )

    project = project_repository.save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    session_repository = SessionRepository(
        database
    )

    session = (
        session_repository.get_or_create_active(
            project_id=project.id,
            channel="telegram",
            user_id="123456",
            conversation_id="654321",
        )
    )

    return session.id


def create_incoming() -> IncomingMessage:
    return IncomingMessage(
        channel=ChannelName.TELEGRAM,
        user_id="123456",
        conversation_id="654321",
        content_type=ContentType.TEXT,
        text="Hola, orquestador.",
        message_id="telegram:654321:1",
        metadata={
            "telegram_username": "jose",
        },
    )


def test_saves_incoming_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        session_id = create_session(database)
        repository = MessageRepository(
            database
        )

        saved = repository.save_incoming(
            session_id=session_id,
            message=create_incoming(),
        )

        assert saved.session_id == session_id
        assert saved.direction == "incoming"
        assert saved.channel == "telegram"
        assert saved.text == "Hola, orquestador."
        assert (
            saved.metadata["telegram_username"]
            == "jose"
        )


def test_saves_outgoing_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        session_id = create_session(database)
        repository = MessageRepository(
            database
        )

        incoming = create_incoming()

        outgoing = OutgoingMessage(
            channel=incoming.channel,
            conversation_id=(
                incoming.conversation_id
            ),
            content_type=ContentType.TEXT,
            correlation_id=incoming.message_id,
            text="Mensaje recibido.",
        )

        saved = repository.save_outgoing(
            session_id=session_id,
            message=outgoing,
        )

        assert saved.direction == "outgoing"
        assert (
            saved.correlation_id
            == incoming.message_id
        )
        assert saved.text == "Mensaje recibido."


def test_does_not_duplicate_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        session_id = create_session(database)
        repository = MessageRepository(
            database
        )
        incoming = create_incoming()

        first = repository.save_incoming(
            session_id,
            incoming,
        )

        second = repository.save_incoming(
            session_id,
            incoming,
        )

        assert second.id == first.id

        messages = repository.list_by_session(
            session_id
        )

        assert len(messages) == 1


def test_lists_messages_in_order() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        session_id = create_session(database)
        repository = MessageRepository(
            database
        )
        incoming = create_incoming()

        repository.save_incoming(
            session_id,
            incoming,
        )

        outgoing = OutgoingMessage(
            channel=incoming.channel,
            conversation_id=(
                incoming.conversation_id
            ),
            content_type=ContentType.TEXT,
            correlation_id=incoming.message_id,
            text="Respuesta del orquestador.",
        )

        repository.save_outgoing(
            session_id,
            outgoing,
        )

        messages = repository.list_by_session(
            session_id
        )

        assert len(messages) == 2
        assert messages[0].direction == "incoming"
        assert messages[1].direction == "outgoing"


def test_recovers_message_by_identifier() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        session_id = create_session(database)
        repository = MessageRepository(
            database
        )
        incoming = create_incoming()

        repository.save_incoming(
            session_id,
            incoming,
        )

        recovered = repository.get_by_message_id(
            channel="telegram",
            message_id=incoming.message_id,
        )

        assert recovered is not None
        assert recovered.message_id == (
            incoming.message_id
        )

def test_lists_messages_by_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        projects = ProjectRepository(
            database
        )

        project_one = projects.save(
            name="Proyecto uno",
            root_path="ruta-uno",
        )

        project_two = projects.save(
            name="Proyecto dos",
            root_path="ruta-dos",
        )

        sessions = SessionRepository(
            database
        )

        session_one = (
            sessions.get_or_create_active(
                project_id=project_one.id,
                channel="telegram",
                user_id="usuario-1",
                conversation_id="conversacion-1",
            )
        )

        session_two = (
            sessions.get_or_create_active(
                project_id=project_two.id,
                channel="telegram",
                user_id="usuario-2",
                conversation_id="conversacion-2",
            )
        )

        repository = MessageRepository(
            database
        )

        message_one = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario-1",
            conversation_id="conversacion-1",
            content_type=ContentType.TEXT,
            text="Mensaje del proyecto uno",
        )

        message_two = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="usuario-2",
            conversation_id="conversacion-2",
            content_type=ContentType.TEXT,
            text="Mensaje del proyecto dos",
        )

        repository.save_incoming(
            session_one.id,
            message_one,
        )
        repository.save_incoming(
            session_two.id,
            message_two,
        )

        result = repository.list_by_project(
            project_id=project_one.id
        )

        assert len(result) == 1
        assert (
            result[0].text
            == "Mensaje del proyecto uno"
        )


def test_rejects_invalid_message_limit() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = MessageRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match="limit debe ser mayor que cero",
        ):
            repository.list_by_project(
                project_id=1,
                limit=0,
            )