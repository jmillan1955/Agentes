from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.attachment import Attachment
from app.models.message_types import (
    ChannelName,
    ContentType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_message_id() -> str:
    return uuid4().hex


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    channel: ChannelName
    user_id: str
    conversation_id: str
    content_type: ContentType

    text: str | None = None
    attachments: tuple[Attachment, ...] = ()
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    message_id: str = field(
        default_factory=new_message_id
    )
    received_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError(
                "message_id no puede estar vacío"
            )

        if not self.user_id.strip():
            raise ValueError(
                "user_id no puede estar vacío"
            )

        if not self.conversation_id.strip():
            raise ValueError(
                "conversation_id no puede estar vacío"
            )

        texto_valido = bool(
            self.text and self.text.strip()
        )

        if not texto_valido and not self.attachments:
            raise ValueError(
                "El mensaje debe contener texto "
                "o algún archivo adjunto"
            )


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    channel: ChannelName
    conversation_id: str
    content_type: ContentType
    correlation_id: str

    text: str | None = None
    attachments: tuple[Attachment, ...] = ()
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    message_id: str = field(
        default_factory=new_message_id
    )
    created_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError(
                "message_id no puede estar vacío"
            )

        if not self.correlation_id.strip():
            raise ValueError(
                "correlation_id no puede estar vacío"
            )

        if not self.conversation_id.strip():
            raise ValueError(
                "conversation_id no puede estar vacío"
            )

        texto_valido = bool(
            self.text and self.text.strip()
        )

        if not texto_valido and not self.attachments:
            raise ValueError(
                "La respuesta debe contener texto "
                "o algún archivo adjunto"
            )