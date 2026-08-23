from __future__ import annotations

from app.context import (
    MessageRepository,
    SessionRepository,
)
from app.models import (
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)


class Orchestrator:
    def __init__(
        self,
        project_id: int,
        session_repository: SessionRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._project_id = project_id
        self._session_repository = (
            session_repository
        )
        self._message_repository = (
            message_repository
        )

    def process(
        self,
        message: IncomingMessage,
    ) -> OutgoingMessage:
        session = (
            self._session_repository
            .get_or_create_active(
                project_id=self._project_id,
                channel=message.channel.value,
                user_id=message.user_id,
                conversation_id=(
                    message.conversation_id
                ),
            )
        )

        self._message_repository.save_incoming(
            session_id=session.id,
            message=message,
        )

        outgoing = self._create_response(
            message=message,
            session_id=session.id,
        )

        self._message_repository.save_outgoing(
            session_id=session.id,
            message=outgoing,
        )

        return outgoing

    @staticmethod
    def _create_response(
        message: IncomingMessage,
        session_id: int,
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
                "processor": (
                    "provisional_orchestrator"
                ),
                "session_id": session_id,
            },
        )