from __future__ import annotations

from app.models import (
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)


class Orchestrator:
    """
    Núcleo provisional del agente.

    En esta primera versión solamente confirma que
    ha recibido correctamente el mensaje.
    """

    def process(
        self,
        message: IncomingMessage,
    ) -> OutgoingMessage:
        if message.content_type != ContentType.TEXT:
            response_text = (
                "He recibido un contenido de tipo "
                f"'{message.content_type.value}'. "
                "Todavía solamente proceso texto."
            )
        else:
            response_text = (
                "He recibido correctamente tu mensaje:\n\n"
                f"{message.text}"
            )

        return OutgoingMessage(
            channel=message.channel,
            conversation_id=message.conversation_id,
            content_type=ContentType.TEXT,
            correlation_id=message.message_id,
            text=response_text,
            metadata={
                "processor": "provisional_orchestrator",
            },
        )