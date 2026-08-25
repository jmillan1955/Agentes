import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.channels.telegram import (
    TelegramChannel,
)
from app.models import (
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)


class RecordingOrchestrator:
    def __init__(self) -> None:
        self.messages: list[IncomingMessage] = []

    def process(
        self,
        message: IncomingMessage,
    ) -> OutgoingMessage:
        self.messages.append(message)

        return OutgoingMessage(
            channel=message.channel,
            conversation_id=(
                message.conversation_id
            ),
            content_type=ContentType.TEXT,
            correlation_id=message.message_id,
            text="Respuesta generada",
            metadata={},
        )


class FakeTranscriptionService:
    def __init__(
        self,
        text: str,
    ) -> None:
        self.text = text
        self.received_paths = []

    def transcribe(self, audio_path) -> str:
        self.received_paths.append(audio_path)
        return self.text


def create_channel(
    orchestrator=None,
    transcription_service=None,
) -> TelegramChannel:
    return TelegramChannel(
        token="token-prueba",
        allowed_user_id=123456,
        orchestrator=(
            orchestrator
            or RecordingOrchestrator()
        ),
        transcription_service=(
            transcription_service
        ),
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

    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(
            id=123456,
            username="jose",
        ),
        effective_chat=SimpleNamespace(
            id=654321,
        ),
    )


def create_command_update(
    text: str,
    message_id: int = 51,
):
    message = SimpleNamespace(
        message_id=message_id,
        text=text,
        voice=None,
        reply_text=AsyncMock(),
    )

    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(
            id=123456,
            username="jose",
        ),
        effective_chat=SimpleNamespace(
            id=654321,
        ),
    )


def create_voice_context(
    user_data: dict | None = None,
):
    telegram_file = SimpleNamespace(
        download_to_drive=AsyncMock(),
    )

    bot = SimpleNamespace(
        get_file=AsyncMock(
            return_value=telegram_file
        ),
    )

    return SimpleNamespace(
        args=[],
        user_data=(
            user_data
            if user_data is not None
            else {}
        ),
        bot=bot,
    )


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

    assert "Tarea #3 seleccionada" in sent_text
    assert "nota de voz" in sent_text


def test_voice_waits_for_confirmation() -> None:
    orchestrator = RecordingOrchestrator()
    transcription = FakeTranscriptionService(
        "Explica qué es SQLite"
    )
    channel = create_channel(
        orchestrator=orchestrator,
        transcription_service=transcription,
    )
    update = create_voice_update()
    context = create_voice_context()

    asyncio.run(
        channel.handle_voice(
            update=update,
            context=context,
        )
    )

    assert orchestrator.messages == []
    assert (
        context.user_data[
            "pending_audio"
        ]["text"]
        == "Explica qué es SQLite"
    )

    replies = [
        call.args[0]
        for call in (
            update.message.reply_text
            .await_args_list
        )
    ]

    assert any(
        "/corregir_audio"
        in reply
        for reply in replies
    )
    assert any(
        "/confirmar_audio"
        in reply
        for reply in replies
    )


def test_confirms_original_transcription() -> None:
    orchestrator = RecordingOrchestrator()
    channel = create_channel(
        orchestrator=orchestrator,
    )
    context = create_voice_context(
        user_data={
            "pending_audio": {
                "text": "Explica qué es SQLite",
                "task_id": None,
                "voice_message_id": 50,
                "voice_duration_seconds": 12,
                "voice_file_unique_id": (
                    "voice-unique-id"
                ),
            }
        }
    )
    update = create_command_update(
        "/confirmar_audio"
    )

    asyncio.run(
        channel.handle_confirm_audio(
            update=update,
            context=context,
        )
    )

    assert len(orchestrator.messages) == 1
    incoming = orchestrator.messages[0]

    assert incoming.text == "Explica qué es SQLite"
    assert incoming.content_type == ContentType.TEXT
    assert (
        incoming.metadata[
            "audio_transcription_corrected"
        ]
        is False
    )
    assert "pending_audio" not in context.user_data


def test_corrects_transcription_before_processing() -> None:
    orchestrator = RecordingOrchestrator()
    channel = create_channel(
        orchestrator=orchestrator,
    )
    context = create_voice_context(
        user_data={
            "pending_audio": {
                "text": (
                    "Qué es el sequel a light"
                ),
                "task_id": None,
                "voice_message_id": 50,
                "voice_duration_seconds": 12,
                "voice_file_unique_id": (
                    "voice-unique-id"
                ),
            }
        }
    )
    context.args = [
        "Explica",
        "en",
        "una",
        "frase",
        "qué",
        "es",
        "SQLite",
    ]
    update = create_command_update(
        "/corregir_audio Explica en una "
        "frase qué es SQLite"
    )

    asyncio.run(
        channel.handle_correct_audio(
            update=update,
            context=context,
        )
    )

    assert len(orchestrator.messages) == 1
    incoming = orchestrator.messages[0]

    assert (
        incoming.text
        == "Explica en una frase qué es SQLite"
    )
    assert (
        incoming.metadata[
            "audio_transcription_corrected"
        ]
        is True
    )
    assert (
        incoming.metadata[
            "original_transcription"
        ]
        == "Qué es el sequel a light"
    )
    assert "pending_audio" not in context.user_data


def test_corrected_audio_keeps_task_id() -> None:
    orchestrator = RecordingOrchestrator()
    channel = create_channel(
        orchestrator=orchestrator,
    )
    context = create_voice_context(
        user_data={
            "pending_audio": {
                "text": "Aclaraciones incorrectas",
                "task_id": 3,
                "voice_message_id": 50,
                "voice_duration_seconds": 12,
                "voice_file_unique_id": (
                    "voice-unique-id"
                ),
            }
        }
    )
    context.args = [
        "Usará",
        "Angular,",
        "FastAPI",
        "y",
        "SQLite",
    ]
    update = create_command_update(
        "/corregir_audio Usará Angular, "
        "FastAPI y SQLite"
    )

    asyncio.run(
        channel.handle_correct_audio(
            update=update,
            context=context,
        )
    )

    assert len(orchestrator.messages) == 1
    incoming = orchestrator.messages[0]

    assert incoming.content_type == ContentType.COMMAND
    assert (
        incoming.text
        == (
            "/responder 3 Usará Angular, "
            "FastAPI y SQLite"
        )
    )
    assert "pending_audio" not in context.user_data


def test_rejects_confirmation_without_audio() -> None:
    orchestrator = RecordingOrchestrator()
    channel = create_channel(
        orchestrator=orchestrator,
    )
    context = create_voice_context()
    update = create_command_update(
        "/confirmar_audio"
    )

    asyncio.run(
        channel.handle_confirm_audio(
            update=update,
            context=context,
        )
    )

    assert orchestrator.messages == []

    sent_text = (
        update.message.reply_text
        .await_args.args[0]
    )

    assert "no hay ninguna" in sent_text.lower()


def test_rejects_empty_audio_correction() -> None:
    orchestrator = RecordingOrchestrator()
    channel = create_channel(
        orchestrator=orchestrator,
    )
    context = create_voice_context(
        user_data={
            "pending_audio": {
                "text": "Texto pendiente",
                "task_id": None,
            }
        }
    )
    context.args = []
    update = create_command_update(
        "/corregir_audio"
    )

    asyncio.run(
        channel.handle_correct_audio(
            update=update,
            context=context,
        )
    )

    assert orchestrator.messages == []
    assert "pending_audio" in context.user_data

    sent_text = (
        update.message.reply_text
        .await_args.args[0]
    )

    assert "texto correcto" in sent_text.lower()

def test_processes_simple_command() -> None:
    orchestrator = RecordingOrchestrator()

    channel = create_channel(
        orchestrator=orchestrator,
    )

    context = create_voice_context()
    context.args = [
        "¿Qué",
        "es",
        "una",
        "cooperativa?",
    ]

    update = create_command_update(
        "/simple ¿Qué es una cooperativa?"
    )

    asyncio.run(
        channel.handle_simple(
            update=update,
            context=context,
        )
    )

    assert len(orchestrator.messages) == 1

    incoming = orchestrator.messages[0]

    assert (
        incoming.text
        == "¿Qué es una cooperativa?"
    )

    assert (
        incoming.content_type
        == ContentType.TEXT
    )

    assert (
        incoming.metadata[
            "response_style"
        ]
        == "simple"
    )

def test_authorizes_second_configured_user() -> None:
    channel = TelegramChannel(
        token="token-prueba",
        allowed_user_id=123456,
        allowed_user_ids=(
            123456,
            234567,
            345678,
            456789,
        ),
        orchestrator=SimpleNamespace(),
    )

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=234567,
        ),
    )

    assert channel.is_authorized(update)


def test_rejects_unconfigured_family_user() -> None:
    channel = TelegramChannel(
        token="token-prueba",
        allowed_user_id=123456,
        allowed_user_ids=(
            123456,
            234567,
            345678,
            456789,
        ),
        orchestrator=SimpleNamespace(),
    )

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=999999,
        ),
    )

    assert not channel.is_authorized(update)