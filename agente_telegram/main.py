import asyncio
import logging
import os
import tempfile
from pathlib import Path
from faster_whisper import WhisperModel

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Evita que las URLs de Telegram y el token aparezcan en el registro.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


USUARIO_AUTORIZADO: int | None = None
MODELO_WHISPER: WhisperModel | None = None

def usuario_autorizado(update: Update) -> bool:
    usuario = update.effective_user

    if usuario is None:
        return False

    autorizado = usuario.id == USUARIO_AUTORIZADO

    if not autorizado:
        logger.warning(
            "Acceso rechazado para el usuario de Telegram %s",
            usuario.id,
        )

    return autorizado


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not usuario_autorizado(update):
        return

    if update.message is None:
        return

    await update.message.reply_text(
        "Hola, José.\n\n"
        "El Agente IA está conectado correctamente.\n"
        "Envíame un mensaje escrito y te lo devolveré como prueba."
    )


async def mostrar_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not usuario_autorizado(update):
        return

    usuario = update.effective_user

    if update.message is None or usuario is None:
        return

    await update.message.reply_text(
        f"Tu identificador de Telegram es:\n\n{usuario.id}"
    )

def transcribir_audio(ruta_audio: Path) -> str:
    if MODELO_WHISPER is None:
        raise RuntimeError("El modelo Whisper no está cargado")

    segmentos, _ = MODELO_WHISPER.transcribe(
        str(ruta_audio),
        language="es",
        beam_size=5,
        vad_filter=True,
    )

    textos = [
        segmento.text.strip()
        for segmento in segmentos
        if segmento.text.strip()
    ]

    return " ".join(textos)

async def recibir_voz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not usuario_autorizado(update):
        return

    if update.message is None or update.message.voice is None:
        return

    voz = update.message.voice

    carpeta_temporal = (
        Path(tempfile.gettempdir()) / "agente_telegram"
    )
    carpeta_temporal.mkdir(parents=True, exist_ok=True)

    ruta_audio = carpeta_temporal / f"{voz.file_unique_id}.ogg"

    await update.message.reply_text(
        "Nota de voz recibida. Descargando el audio..."
    )

    try:
        archivo_telegram = await context.bot.get_file(voz.file_id)

        await archivo_telegram.download_to_drive(
            custom_path=ruta_audio
        )

        tamano_kb = ruta_audio.stat().st_size / 1024

        logger.info(
            "Audio descargado: duración=%s segundos, tamaño=%.1f KB",
            voz.duration,
            tamano_kb,
        )

        await update.message.reply_text(
            "Audio descargado. Transcribiendo..."
        )

        texto = await asyncio.to_thread(
            transcribir_audio,
            ruta_audio,
        )

        if not texto:
            await update.message.reply_text(
                "No he podido reconocer texto en la nota de voz."
            )
            return

        logger.info(
            "Audio transcrito correctamente: %s caracteres",
            len(texto),
        )

        await update.message.reply_text(
            "Texto reconocido:\n\n"
            f"{texto}"
        )

    except Exception as error:
        logger.error(
            "No se pudo procesar el audio: %s",
            type(error).__name__,
        )

        await update.message.reply_text(
            "No se ha podido procesar la nota de voz."
        )

    finally:
        ruta_audio.unlink(missing_ok=True)

async def responder_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not usuario_autorizado(update):
        return

    if update.message is None or update.message.text is None:
        return

    texto = update.message.text

    await update.message.reply_text(
        f"He recibido este texto:\n\n{texto}"
    )


def main() -> None:
    global USUARIO_AUTORIZADO, MODELO_WHISPER

    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    usuario_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")

    logger.info("Cargando el modelo Whisper small...")

    MODELO_WHISPER = WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
    )

    logger.info("Modelo Whisper cargado correctamente")

    if not token:
        raise RuntimeError(
            "No se encontró TELEGRAM_BOT_TOKEN en el archivo .env"
        )

    if not usuario_id:
        raise RuntimeError(
            "No se encontró TELEGRAM_ALLOWED_USER_ID en el archivo .env"
        )

    try:
        USUARIO_AUTORIZADO = int(usuario_id)
    except ValueError as error:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_ID debe ser un número entero"
        ) from error

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mi_id", mostrar_id))

    application.add_handler(
        MessageHandler(filters.VOICE, recibir_voz)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            responder_texto,
        )
    )

    logger.info("Iniciando Agente Telegram...")
    logger.info("Control de acceso activado")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()