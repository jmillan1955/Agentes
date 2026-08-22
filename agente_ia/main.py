from __future__ import annotations

import argparse
import logging

from app.orchestrator import Orchestrator
from app.transcription_service import (
    TranscriptionService,
)
from channels.console_channel import ConsoleChannel
from channels.telegram_channel import TelegramChannel
from config import Settings
from providers.ollama_provider import OllamaProvider


logging.basicConfig(
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(
    logging.WARNING
)
logging.getLogger("httpcore").setLevel(
    logging.WARNING
)


def obtener_argumentos(
    canal_predeterminado: str,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agente IA"
    )

    parser.add_argument(
        "--canal",
        choices=["consola", "telegram"],
        default=canal_predeterminado,
        help=(
            "Canal de entrada y salida. "
            f"Predeterminado: {canal_predeterminado}"
        ),
    )

    return parser.parse_args()


def crear_orchestrator(
    settings: Settings,
) -> Orchestrator:
    provider = OllamaProvider(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
    )

    return Orchestrator(
        language_provider=provider
    )


def main() -> None:
    settings = Settings.cargar()

    argumentos = obtener_argumentos(
        settings.canal_predeterminado
    )

    orchestrator = crear_orchestrator(
        settings
    )

    if argumentos.canal == "consola":
        canal = ConsoleChannel(
            settings=settings,
            orchestrator=orchestrator,
        )

        canal.ejecutar()
        return

    if not settings.telegram_bot_token:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN en .env"
        )

    if settings.telegram_allowed_user_id is None:
        raise RuntimeError(
            "Falta TELEGRAM_ALLOWED_USER_ID en .env"
        )

    transcription_service = (
        TranscriptionService(
            model_name=settings.whisper_model,
        )
    )

    canal = TelegramChannel(
        token=settings.telegram_bot_token,
        allowed_user_id=(
            settings.telegram_allowed_user_id
        ),
        orchestrator=orchestrator,
        transcription_service=(
            transcription_service
        ),
    )

    canal.ejecutar()


if __name__ == "__main__":
    main()