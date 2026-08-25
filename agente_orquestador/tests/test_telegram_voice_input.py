import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.channels.telegram import (
    TelegramChannel,
)
from app.models import ContentType


def create_channel() -> TelegramChannel:
    return TelegramChannel(
        token="token-prueba",
        allowed_user_id=123456,
        orchestrator=SimpleNamespace(),
    )


def create_voice_update():
    voice = SimpleNamespace(
        duration=12,
        file_id="voice-file-id",
        file_unique_id="voice-unique-id",
    )

    message = SimpleNamespace(
        message_id=50,
        text=None,
        voice=voice,
        reply_text=AsyncMock(),
    )

    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(
            id=123456,
            username="jose",
        ),
        effective_chat=SimpleNamespace(
            id=654321,
        ),
    )

    return update


def test_creates_text_message_from_voice() -> None:
    channel = create_channel()
    update = create_voice_update()

    incoming = (
        channel.create_incoming_from_voice(
            update=update,
            text=(
                "Crea el proyecto "
                "puntuacion_padel"
            ),
            content_type=ContentType.TEXT,
        )
    )

    assert (
        incoming.text
        == "Crea el proyecto puntuacion_padel"
    )

    assert (
        incoming.content_type
        == ContentType.TEXT
    )

    assert (
        incoming.message_id
        == "telegram:654321:50"
    )

    assert (
        incoming.metadata[
            "source_content_type"
        ]
        == "voice"
    )

    assert (
        incoming.metadata[
            "voice_duration_seconds"
        ]
        == 12
    )

    assert (
        incoming.metadata[
            "voice_file_unique_id"
        ]
        == "voice-unique-id"
    )


def test_creates_respond_command_from_voice() -> None:
    channel = create_channel()
    update = create_voice_update()

    incoming = (
        channel.create_incoming_from_voice(
            update=update,
            text=(
                "/responder 3 La aplicación "
                "utilizará Angular y FastAPI"
            ),
            content_type=ContentType.COMMAND,
        )
    )

    assert (
        incoming.content_type
        == ContentType.COMMAND
    )

    assert incoming.text is not None

    assert incoming.text.startswith(
        "/responder 3 "
    )

    assert (
        "Angular y FastAPI"
        in incoming.text
    )


def test_selects_task_for_next_voice() -> None:
    channel = create_channel()
    update = create_voice_update()

    context = SimpleNamespace(
        args=["3"],
        user_data={},
    )

    asyncio.run(
        channel.handle_respond(
            update=update,
            context=context,
        )
    )

    assert (
        context.user_data[
            "pending_audio_task_id"
        ]
        == 3
    )

    update.message.reply_text.assert_awaited_once()

    sent_text = (
        update.message.reply_text
        .await_args.args[0]
    )

    assert (
        "Tarea #3 seleccionada"
        in sent_text
    )

    assert (
        "Envía ahora una nota de voz"
        in sent_text
    )