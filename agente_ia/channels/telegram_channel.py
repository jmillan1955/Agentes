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

from app.models import Peticion, TipoEntrada
from app.orchestrator import Orchestrator
from app.transcription_service import TranscriptionService


logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(
        self,
        token: str,
        allowed_user_id: int,
        orchestrator: Orchestrator,
        transcription_service: TranscriptionService,
    ) -> None:
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.orchestrator = orchestrator
        self.transcription_service = transcription_service

    def ejecutar(self) -> None:
        application = (
            Application.builder()
            .token(self.token)
            .build()
        )

        application.add_handler(
            CommandHandler("start", self.start)
        )
        application.add_handler(
            CommandHandler("mi_id", self.mostrar_id)
        )
        application.add_handler(
            MessageHandler(
                filters.VOICE,
                self.recibir_voz,
            )
        )
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.recibir_texto,
            )
        )

        logger.info("Iniciando canal Telegram")
        logger.info("Control de acceso activado")

        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    def usuario_autorizado(
        self,
        update: Update,
    ) -> bool:
        usuario = update.effective_user

        if usuario is None:
            return False

        autorizado = (
            usuario.id == self.allowed_user_id
        )

        if not autorizado:
            logger.warning(
                "Acceso rechazado para el usuario %s",
                usuario.id,
            )

        return autorizado

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return

        if update.message is None:
            return

        await update.message.reply_text(
            "Hola, José.\n\n"
            "El Agente IA está conectado.\n"
            "Puedes enviarme texto o una nota de voz."
        )

    async def mostrar_id(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return

        usuario = update.effective_user

        if update.message is None or usuario is None:
            return

        await update.message.reply_text(
            f"Tu identificador de Telegram es:\n\n"
            f"{usuario.id}"
        )

    async def recibir_texto(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return

        if (
            update.message is None
            or update.message.text is None
        ):
            return

        peticion = Peticion(
            contenido=update.message.text,
            canal="telegram",
            tipo=TipoEntrada.TEXTO,
            metadatos={
                "telegram_user_id": (
                    update.effective_user.id
                    if update.effective_user
                    else None
                ),
            },
        )

        await self._procesar_peticion(
            update,
            peticion,
        )

    async def recibir_voz(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return

        if (
            update.message is None
            or update.message.voice is None
        ):
            return

        voz = update.message.voice

        carpeta_temporal = (
            Path(tempfile.gettempdir())
            / "agente_ia"
            / "telegram"
        )
        carpeta_temporal.mkdir(
            parents=True,
            exist_ok=True,
        )

        ruta_audio = (
            carpeta_temporal
            / f"{voz.file_unique_id}.ogg"
        )

        await update.message.reply_text(
            "Nota de voz recibida. Transcribiendo..."
        )

        try:
            archivo = await context.bot.get_file(
                voz.file_id
            )

            await archivo.download_to_drive(
                custom_path=ruta_audio
            )

            texto = await asyncio.to_thread(
                self.transcription_service.transcribir,
                ruta_audio,
            )

            if not texto:
                await update.message.reply_text(
                    "No he podido reconocer texto "
                    "en la nota de voz."
                )
                return

            logger.info(
                "Audio transcrito: %s caracteres",
                len(texto),
            )

            await update.message.reply_text(
                "Texto reconocido:\n\n"
                f"{texto}"
            )

            peticion = Peticion(
                contenido=texto,
                canal="telegram",
                tipo=TipoEntrada.AUDIO,
                archivos=[str(ruta_audio)],
                metadatos={
                    "duracion_segundos": voz.duration,
                    "telegram_user_id": (
                        update.effective_user.id
                        if update.effective_user
                        else None
                    ),
                },
            )

            await self._procesar_peticion(
                update,
                peticion,
            )

        except Exception:
            logger.exception(
                "No se pudo procesar la nota de voz"
            )

            await update.message.reply_text(
                "No se ha podido procesar "
                "la nota de voz."
            )

        finally:
            ruta_audio.unlink(missing_ok=True)

    async def _procesar_peticion(
        self,
        update: Update,
        peticion: Peticion,
    ) -> None:
        if update.message is None:
            return

        await update.message.reply_text(
            "Consultando al Agente IA..."
        )

        respuesta = await asyncio.to_thread(
            self.orchestrator.procesar,
            peticion,
        )

        await self._enviar_texto(
            update,
            respuesta.contenido,
        )

    @staticmethod
    async def _enviar_texto(
        update: Update,
        texto: str,
    ) -> None:
        if update.message is None:
            return

        limite = 4000

        for inicio in range(0, len(texto), limite):
            fragmento = texto[
                inicio:inicio + limite
            ]

            await update.message.reply_text(
                fragmento
            )