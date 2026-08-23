from app.models import (
    Attachment,
    ChannelName,
    ContentType,
    IncomingMessage,
)
from app.orchestrator import Orchestrator


def test_procesa_mensaje_de_texto() -> None:
    orchestrator = Orchestrator()

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
    assert outgoing.content_type == ContentType.TEXT
    assert outgoing.text is not None
    assert "Hola, agente." in outgoing.text
    assert (
        outgoing.metadata["processor"]
        == "provisional_orchestrator"
    )


def test_informa_si_recibe_otro_tipo() -> None:
    orchestrator = Orchestrator()

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
    assert "solamente proceso texto" in outgoing.text