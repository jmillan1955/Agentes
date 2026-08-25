from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.audio import TranscriptionService
from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)
from app.orchestrator import Orchestrator


logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(
        self,
        token: str,
        allowed_user_id: int,
        orchestrator: Orchestrator,
        transcription_service: (
            TranscriptionService | None
        ) = None,
    ) -> None:
        self._token = token
        self._allowed_user_id = (
            allowed_user_id
        )
        self._orchestrator = orchestrator
        self._transcription_service = (
            transcription_service
        )

    def run(self) -> None:
        application = (
            Application.builder()
            .token(self._token)
            .build()
        )

        application.add_handler(
            CommandHandler(
                "start",
                self.handle_start,
            )
        )

        application.add_handler(
            CommandHandler(
                "contexto",
                self.handle_context,
            )
        )

        application.add_handler(
            CommandHandler(
                "buscar",
                self.handle_search,
            )
        )

        application.add_handler(
            CommandHandler(
                "clasificar",
                self.handle_classify,
            )
        )

        application.add_handler(
            CommandHandler(
                "responder",
                self.handle_respond,
            )
        )

        application.add_handler(
            MessageHandler(
                filters.VOICE,
                self.handle_voice,
            )
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text,
            )
        )

        application.add_error_handler(
            self.handle_error
        )

        logger.info(
            "Iniciando canal Telegram"
        )

        logger.info(
            "Control de acceso activado"
        )

        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    def is_authorized(
        self,
        update: Update,
    ) -> bool:
        user = update.effective_user

        if user is None:
            return False

        authorized = (
            user.id
            == self._allowed_user_id
        )

        if not authorized:
            logger.warning(
                "Acceso rechazado para "
                "el usuario %s",
                user.id,
            )

        return authorized

    async def handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.is_authorized(update):
            return

        if update.message is None:
            return

        await update.message.reply_text(
            "Agente Orquestador conectado.\n\n"
            "Puedes enviar texto o una "
            "nota de voz.\n\n"
            "Comandos disponibles:\n"
            "/contexto\n"
            "/buscar <consulta>\n"
            "/clasificar <petición>\n"
            (
                "/responder <tarea_id> "
                "<aclaraciones>\n"
            )
            (
                "/responder <tarea_id> "
                "y después una nota de voz"
            )
        )

    async def handle_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.TEXT,
        )

    async def handle_context(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
        )

    async def handle_search(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
        )

    async def handle_classify(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
        )

    async def handle_respond(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.is_authorized(update):
            return

        if update.message is None:
            return

        arguments = list(
            context.args or []
        )

        if len(arguments) == 1:
            task_id_text = arguments[0].strip()

            try:
                task_id = int(task_id_text)

            except ValueError:
                await update.message.reply_text(
                    "El identificador de la tarea "
                    "debe ser un número entero."
                )
                return

            if task_id <= 0:
                await update.message.reply_text(
                    "El identificador de la tarea "
                    "debe ser mayor que cero."
                )
                return

            context.user_data[
                "pending_audio_task_id"
            ] = task_id

            await update.message.reply_text(
                f"Tarea #{task_id} seleccionada.\n\n"
                "Envía ahora una nota de voz "
                "con tus aclaraciones."
            )
            return

        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
        )

    async def handle_voice(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.is_authorized(update):
            return

        if (
            update.message is None
            or update.message.voice is None
        ):
            return

        if self._transcription_service is None:
            await update.message.reply_text(
                "El servicio de transcripción "
                "no está configurado."
            )
            return

        voice = update.message.voice

        temporary_directory = (
            Path(tempfile.gettempdir())
            / "agente_orquestador"
            / "telegram"
        )

        temporary_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        audio_path = (
            temporary_directory
            / f"{voice.file_unique_id}.ogg"
        )

        await update.message.reply_text(
            "Nota de voz recibida. "
            "Transcribiendo..."
        )

        try:
            telegram_file = (
                await context.bot.get_file(
                    voice.file_id
                )
            )

            await telegram_file.download_to_drive(
                custom_path=audio_path
            )

            text = await asyncio.to_thread(
                self._transcription_service
                .transcribe,
                audio_path,
            )

            if not text:
                await update.message.reply_text(
                    "No he podido reconocer texto "
                    "en la nota de voz."
                )
                return

            logger.info(
                "Audio transcrito: %s caracteres",
                len(text),
            )

            await update.message.reply_text(
                "Texto reconocido:\n\n"
                f"{text}"
            )

            pending_task_id = (
                context.user_data.pop(
                    "pending_audio_task_id",
                    None,
                )
            )

            if isinstance(
                pending_task_id,
                int,
            ):
                normalized_text = (
                    f"/responder "
                    f"{pending_task_id} "
                    f"{text}"
                )

                content_type = (
                    ContentType.COMMAND
                )

                progress_text = (
                    "Aclaración transcrita. "
                    "Generando planificación..."
                )

            else:
                normalized_text = text
                content_type = ContentType.TEXT

                progress_text = (
                    "Transcripción completada. "
                    "Procesando petición..."
                )

            incoming = (
                self.create_incoming_from_voice(
                    update=update,
                    text=normalized_text,
                    content_type=content_type,
                )
            )

            await self._execute_incoming(
                update=update,
                incoming=incoming,
                progress_text=progress_text,
            )

        except Exception:
            logger.exception(
                "No se pudo procesar "
                "la nota de voz"
            )

            await update.message.reply_text(
                "No se ha podido procesar "
                "la nota de voz."
            )

        finally:
            audio_path.unlink(
                missing_ok=True
            )

    async def _process_update(
        self,
        update: Update,
        content_type: ContentType,
    ) -> None:
        if not self.is_authorized(update):
            return

        try:
            incoming = self.create_incoming(
                update=update,
                content_type=content_type,
            )

            is_planning_command = (
                content_type
                == ContentType.COMMAND
                and incoming.text is not None
                and (
                    incoming.text
                    .strip()
                    .lower()
                    .startswith("/responder")
                )
            )

            progress_text: str | None = None

            if content_type == ContentType.TEXT:
                progress_text = (
                    "Petición recibida. "
                    "Procesando..."
                )

            elif is_planning_command:
                progress_text = (
                    "Aclaración recibida. "
                    "Generando planificación..."
                )

            await self._execute_incoming(
                update=update,
                incoming=incoming,
                progress_text=progress_text,
            )

        except Exception:
            logger.exception(
                "No se pudo procesar "
                "el mensaje de Telegram"
            )

            if update.message is not None:
                await update.message.reply_text(
                    "No se ha podido procesar "
                    "el mensaje."
                )

    async def _execute_incoming(
        self,
        update: Update,
        incoming: IncomingMessage,
        progress_text: str | None,
    ) -> None:
        logger.info(
            "Mensaje recibido: tipo=%s, id=%s",
            incoming.content_type.value,
            incoming.message_id,
        )

        if (
            progress_text is not None
            and update.message is not None
        ):
            await update.message.reply_text(
                progress_text
            )

            logger.info(
                "Generando respuesta para %s",
                incoming.message_id,
            )

            outgoing = await asyncio.to_thread(
                self._orchestrator.process,
                incoming,
            )

            logger.info(
                "Petición procesada para %s "
                "en %s segundos",
                incoming.message_id,
                outgoing.metadata.get(
                    "elapsed_seconds",
                    "desconocido",
                ),
            )

        else:
            outgoing = self._orchestrator.process(
                incoming
            )

        await self.send_outgoing(
            update=update,
            outgoing=outgoing,
        )

    def create_incoming(
        self,
        update: Update,
        content_type: ContentType = (
            ContentType.TEXT
        ),
    ) -> IncomingMessage:
        message = update.message
        user = update.effective_user
        chat = update.effective_chat

        if (
            message is None
            or message.text is None
            or user is None
            or chat is None
        ):
            raise ValueError(
                "La actualización de Telegram "
                "no contiene un mensaje "
                "de texto válido"
            )

        return IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id=str(user.id),
            conversation_id=str(chat.id),
            content_type=content_type,
            text=message.text,
            message_id=(
                f"telegram:{chat.id}:"
                f"{message.message_id}"
            ),
            metadata={
                "telegram_message_id": (
                    message.message_id
                ),
                "telegram_username": (
                    user.username
                ),
                "source_content_type": (
                    "text"
                ),
            },
        )

    def create_incoming_from_voice(
        self,
        update: Update,
        text: str,
        content_type: ContentType,
    ) -> IncomingMessage:
        message = update.message
        user = update.effective_user
        chat = update.effective_chat

        if (
            message is None
            or message.voice is None
            or user is None
            or chat is None
        ):
            raise ValueError(
                "La actualización de Telegram "
                "no contiene una nota "
                "de voz válida"
            )

        voice = message.voice

        return IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id=str(user.id),
            conversation_id=str(chat.id),
            content_type=content_type,
            text=text,
            message_id=(
                f"telegram:{chat.id}:"
                f"{message.message_id}"
            ),
            metadata={
                "telegram_message_id": (
                    message.message_id
                ),
                "telegram_username": (
                    user.username
                ),
                "source_content_type": (
                    "voice"
                ),
                "voice_duration_seconds": (
                    voice.duration
                ),
                "voice_file_unique_id": (
                    voice.file_unique_id
                ),
            },
        )

    @staticmethod
    def format_outgoing_text(
        outgoing: OutgoingMessage,
    ) -> str:
        text = outgoing.text or ""

        elapsed = outgoing.metadata.get(
            "elapsed_seconds"
        )

        if not isinstance(
            elapsed,
            (int, float),
        ):
            return text

        minutes = elapsed / 60

        formatted_minutes = (
            f"{minutes:.2f}"
            .replace(".", ",")
        )

        lines = [
            text,
            "",
            (
                "⏱ Tiempo de ejecución: "
                f"{formatted_minutes} minutos"
            ),
        ]

        model = outgoing.metadata.get(
            "model"
        )

        if isinstance(model, str) and model:
            lines.append(
                f"🤖 Modelo: {model}"
            )

        return "\n".join(lines)

    async def send_outgoing(
        self,
        update: Update,
        outgoing: OutgoingMessage,
    ) -> None:
        if update.message is None:
            return

        if outgoing.text is None:
            return

        formatted_text = (
            self.format_outgoing_text(
                outgoing
            )
        )

        telegram_limit = 4000

        logger.info(
            "Enviando respuesta a Telegram: "
            "%s caracteres",
            len(formatted_text),
        )

        for start in range(
            0,
            len(formatted_text),
            telegram_limit,
        ):
            fragment = formatted_text[
                start:start + telegram_limit
            ]

            await update.message.reply_text(
                fragment
            )

        logger.info(
            "Respuesta enviada correctamente "
            "a Telegram"
        )

    async def handle_error(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        logger.error(
            "Error no controlado en Telegram",
            exc_info=context.error,
        )