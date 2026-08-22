from __future__ import annotations

import asyncio
import json
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
from app.text_to_speech_service import (
    TextToSpeechError,
    TextToSpeechService,
)

logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(
        self,
        token: str,
        allowed_user_id: int,
        orchestrator: Orchestrator,
        transcription_service: TranscriptionService,
        text_to_speech_service: TextToSpeechService,
    ) -> None:
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.orchestrator = orchestrator
        self.transcription_service = transcription_service
        self.text_to_speech_service = (
            text_to_speech_service
        )

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
                filters.Document.ALL,
                self.recibir_documento,
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
            "Puedes enviarme:\n"
            "- Un mensaje de texto.\n"
            "- Una nota de voz.\n"
            "- Un fichero TXT para convertirlo en MP3."
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


    def _obtener_voz_documento(
        self,
        caption: str | None,
    ) -> str:
        if not caption:
            return self.text_to_speech_service.voice

        for linea in caption.splitlines():
            clave, separador, valor = linea.partition("=")

            if (
                separador
                and clave.strip().lower() == "voz"
            ):
                return valor.strip().lower()

        return self.text_to_speech_service.voice


    async def recibir_documento(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return

        if (
            update.message is None
            or update.message.document is None
        ):
            return

        documento = update.message.document
        nombre_original = (
            documento.file_name or "texto.txt"
        )
        nombre_seguro = Path(nombre_original).name

        voz_seleccionada = (
            self._obtener_voz_documento(
                update.message.caption
            )
        )

        if (
            voz_seleccionada
            not in self.text_to_speech_service.VOCES_ESPANOLAS
        ):
            voces = ", ".join(
                sorted(
                    self.text_to_speech_service.VOCES_ESPANOLAS
                )
            )

            await update.message.reply_text(
                f"La voz '{voz_seleccionada}' "
                "no está disponible.\n\n"
                f"Voces disponibles: {voces}"
            )
            return



        if Path(nombre_seguro).suffix.lower() != ".txt":
            await update.message.reply_text(
                "Por ahora solamente puedo convertir "
                "ficheros con extensión .txt."
            )
            return

        limite_bytes = 1_000_000

        if (
            documento.file_size is not None
            and documento.file_size > limite_bytes
        ):
            await update.message.reply_text(
                "El fichero es demasiado grande. "
                "El límite actual es de 1 MB."
            )
            return

        await update.message.reply_text(
            f"Fichero recibido: {nombre_seguro}\n"
            "Preparando la conversión a MP3..."
        )

        try:
            with tempfile.TemporaryDirectory(
                prefix="agente_ia_telegram_tts_"
            ) as carpeta_temporal:
                carpeta = Path(carpeta_temporal)

                ruta_texto = (
                    carpeta
                    / f"{documento.file_unique_id}.txt"
                )

                nombre_base = (
                    Path(nombre_seguro).stem.strip()
                    or "audio"
                )

                ruta_mp3 = (
                    carpeta / f"{nombre_base}.mp3"
                )

                archivo_telegram = (
                    await context.bot.get_file(
                        documento.file_id
                    )
                )

                await archivo_telegram.download_to_drive(
                    custom_path=ruta_texto
                )

                try:
                    texto = ruta_texto.read_text(
                        encoding="utf-8-sig"
                    ).strip()
                except UnicodeDecodeError:
                    await update.message.reply_text(
                        "No he podido leer el fichero. "
                        "Debe estar guardado en formato UTF-8."
                    )
                    return

                if not texto:
                    await update.message.reply_text(
                        "El fichero de texto está vacío."
                    )
                    return

                if (
                    len(texto)
                    > self.text_to_speech_service.max_characters
                ):
                    await update.message.reply_text(
                        "El texto contiene "
                        f"{len(texto)} caracteres y supera "
                        "el límite de "
                        f"{self.text_to_speech_service.max_characters}."
                    )
                    return

                await update.message.reply_text(
                    f"Texto leído: {len(texto)} caracteres.\n"
                    "Generando el audio con Kokoro..."
                )

                inicio = asyncio.get_running_loop().time()

                await asyncio.to_thread(
                    self.text_to_speech_service.generar_mp3,
                    texto,
                    ruta_mp3,
                    voice=voz_seleccionada,
                )

                tiempo = (
                    asyncio.get_running_loop().time()
                    - inicio
                )

                logger.info(
                    "MP3 generado: caracteres=%s, "
                    "voz=%s, tiempo=%.3f segundos",
                    len(texto),
                    voz_seleccionada,
                    tiempo,
                )

                with ruta_mp3.open("rb") as archivo_mp3:
                    await update.message.reply_document(
                        document=archivo_mp3,
                        filename=ruta_mp3.name,
                        caption=(
                            "Audio generado con Kokoro.\n"
                            f"Voz: "
                            f"{voz_seleccionada}\n"
                            f"Tiempo de ejecución: "
                            f"{tiempo:.3f} segundos"
                        ),
                    )

        except TextToSpeechError as error:
            logger.warning(
                "Error controlado al generar el MP3: %s",
                error,
            )

            await update.message.reply_text(
                f"No se ha podido generar el audio.\n\n"
                f"{error}"
            )

        except Exception:
            logger.exception(
                "No se pudo procesar el fichero de texto"
            )

            await update.message.reply_text(
                "No se ha podido procesar "
                "el fichero de texto."
            )


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




        texto_salida = self._formatear_respuesta(
            respuesta.contenido
        )

        await self._enviar_texto(
            update=update,
            texto=texto_salida,
        )


    @staticmethod
    def _formatear_respuesta(
        contenido: str,
    ) -> str:
        """
        Convierte la respuesta JSON interna en un mensaje
        legible para Telegram.
        """
        try:
            datos = json.loads(contenido)
        except (json.JSONDecodeError, TypeError):
            return contenido

        respuesta = datos.get("respuesta")

        if not isinstance(respuesta, str):
            return contenido

        # Convierte posibles secuencias literales \n
        # en saltos de línea reales.
        respuesta = respuesta.replace(
            "\\n",
            "\n",
        ).strip()

        tiempo = datos.get(
            "tiempo_ejecución_segundos"
        )

        if tiempo is None:
            tiempo = datos.get(
                "tiempo_ejecucion_segundos"
            )

        if isinstance(tiempo, (int, float)):
            return (
                f"{respuesta}\n\n"
                f"⏱ Tiempo de ejecución: "
                f"{tiempo:.3f} segundos"
            )

        return respuesta


    async def _enviar_texto(
        self,
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