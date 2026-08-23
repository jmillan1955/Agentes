from types import SimpleNamespace
from app.context import (
    ContextDatabase,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
)
from app.models import (
    ChannelName,
    ContentType,
)
from app.orchestrator import Orchestrator
from app.channels.telegram import TelegramChannel

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

    orchestrator = Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=MessageRepository(
            database
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
    assert incoming.conversation_id == "654321"
    assert incoming.text == "Hola, orquestador"
    assert incoming.message_id == (
        "telegram:654321:42"
    )