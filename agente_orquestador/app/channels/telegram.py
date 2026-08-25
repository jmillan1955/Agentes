from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    ) -> None:
        self._token = token
        self._allowed_user_id = allowed_user_id
        self._orchestrator = orchestrator

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
            user.id == self._allowed_user_id
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
            "Hito 1: recepción y respuesta "
            "de mensajes de texto."
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

    async def handle_classify(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
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

            logger.info(
                "Mensaje recibido: tipo=%s, id=%s",
                content_type.value,
                incoming.message_id,
            )

            if (
                content_type
                == ContentType.TEXT
                and update.message is not None
            ):
                await update.message.reply_text(
                    "Petición recibida. "
                    "Procesando..."
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
                outgoing = (
                    self._orchestrator.process(
                        incoming
                    )
                )
            await self.send_outgoing(
                update=update,
                outgoing=outgoing,
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

    def create_incoming(
        self,
        update: Update,
        content_type: ContentType = ContentType.TEXT,
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
                "no contiene un mensaje de texto válido"
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

    async def handle_search(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._process_update(
            update=update,
            content_type=ContentType.COMMAND,
        )