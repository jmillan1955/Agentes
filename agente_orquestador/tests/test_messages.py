import pytest

from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)


def test_crea_mensaje_de_entrada_telegram() -> None:
    mensaje = IncomingMessage(
        channel=ChannelName.TELEGRAM,
        user_id="123456",
        conversation_id="123456",
        content_type=ContentType.TEXT,
        text="¿Cuáles son los ríos más caudalosos?",
    )

    assert mensaje.channel == ChannelName.TELEGRAM
    assert mensaje.content_type == ContentType.TEXT
    assert mensaje.text is not None
    assert mensaje.message_id
    assert mensaje.received_at.tzinfo is not None


def test_crea_respuesta_relacionada() -> None:
    entrada = IncomingMessage(
        channel=ChannelName.TELEGRAM,
        user_id="123456",
        conversation_id="123456",
        content_type=ContentType.TEXT,
        text="Hola",
    )

    salida = OutgoingMessage(
        channel=entrada.channel,
        conversation_id=entrada.conversation_id,
        content_type=ContentType.TEXT,
        correlation_id=entrada.message_id,
        text="Hola, mensaje recibido.",
    )

    assert salida.correlation_id == entrada.message_id
    assert salida.channel == entrada.channel
    assert salida.conversation_id == (
        entrada.conversation_id
    )


def test_rechaza_entrada_sin_contenido() -> None:
    with pytest.raises(
        ValueError,
        match="texto o algún archivo",
    ):
        IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="123456",
            content_type=ContentType.TEXT,
        )


def test_rechaza_salida_sin_contenido() -> None:
    with pytest.raises(
        ValueError,
        match="texto o algún archivo",
    ):
        OutgoingMessage(
            channel=ChannelName.TELEGRAM,
            conversation_id="123456",
            content_type=ContentType.TEXT,
            correlation_id="mensaje-original",
        )