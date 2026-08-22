from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    nombre: str
    version: str
    entorno: str

    canal_predeterminado: str

    ollama_url: str
    ollama_model: str

    telegram_bot_token: str | None
    telegram_allowed_user_id: int | None

    whisper_model: str
    docs_dir: Path

    @classmethod
    def cargar(cls) -> "Settings":
        telegram_user_id = os.getenv(
            "TELEGRAM_ALLOWED_USER_ID"
        )

        if telegram_user_id:
            try:
                telegram_allowed_user_id = int(
                    telegram_user_id
                )
            except ValueError as error:
                raise RuntimeError(
                    "TELEGRAM_ALLOWED_USER_ID debe "
                    "ser un número entero"
                ) from error
        else:
            telegram_allowed_user_id = None

        canal_predeterminado = os.getenv(
            "AGENTE_CANAL",
            "telegram",
        ).lower()

        if canal_predeterminado not in {
            "consola",
            "telegram",
        }:
            raise RuntimeError(
                "AGENTE_CANAL debe ser "
                "'consola' o 'telegram'"
            )

        return cls(
            nombre=os.getenv(
                "AGENTE_NOMBRE",
                "Agente IA",
            ),
            version=os.getenv(
                "AGENTE_VERSION",
                "0.3.0",
            ),
            entorno=os.getenv(
                "AGENTE_ENTORNO",
                "desarrollo",
            ),
            canal_predeterminado=(
                canal_predeterminado
            ),
            ollama_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://192.168.1.131:11434",
            ),
            ollama_model=os.getenv(
                "OLLAMA_MODEL",
                "qwen3:4b",
            ),
            telegram_bot_token=os.getenv(
                "TELEGRAM_BOT_TOKEN"
            ),
            telegram_allowed_user_id=(
                telegram_allowed_user_id
            ),
            whisper_model=os.getenv(
                "WHISPER_MODEL",
                "small",
            ),
            docs_dir=BASE_DIR / "docs",
        )