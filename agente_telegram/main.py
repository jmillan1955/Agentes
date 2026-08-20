import logging
import os

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
    global USUARIO_AUTORIZADO

    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    usuario_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")

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
        MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto)
    )

    logger.info("Iniciando Agente Telegram...")
    logger.info("Control de acceso activado")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()