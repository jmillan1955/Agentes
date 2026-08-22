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

    tts_provider: str
    kokoro_voice: str
    kokoro_speed: float
    tts_max_characters: int

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

        tts_provider = os.getenv(
            "TTS_PROVIDER",
            "kokoro",
        ).lower()

        if tts_provider != "kokoro":
            raise RuntimeError(
                "TTS_PROVIDER debe ser 'kokoro'"
            )

        kokoro_voice = os.getenv(
            "KOKORO_VOICE",
            "ef_dora",
        )

        if kokoro_voice not in {
            "ef_dora",
            "em_alex",
            "em_santa",
        }:
            raise RuntimeError(
                "KOKORO_VOICE debe ser "
                "'ef_dora', 'em_alex' o 'em_santa'"
            )

        try:
            kokoro_speed = float(
                os.getenv(
                    "KOKORO_SPEED",
                    "1.0",
                )
            )
        except ValueError as error:
            raise RuntimeError(
                "KOKORO_SPEED debe ser un número"
            ) from error

        if not 0.5 <= kokoro_speed <= 2.0:
            raise RuntimeError(
                "KOKORO_SPEED debe estar "
                "entre 0.5 y 2.0"
            )

        try:
            tts_max_characters = int(
                os.getenv(
                    "TTS_MAX_CHARACTERS",
                    "20000",
                )
            )
        except ValueError as error:
            raise RuntimeError(
                "TTS_MAX_CHARACTERS debe "
                "ser un número entero"
            ) from error

        if tts_max_characters <= 0:
            raise RuntimeError(
                "TTS_MAX_CHARACTERS debe "
                "ser mayor que cero"
            )

        return cls(
            nombre=os.getenv(
                "AGENTE_NOMBRE",
                "Agente IA",
            ),
            version=os.getenv(
                "AGENTE_VERSION",
                "0.4.0",
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
            tts_provider=tts_provider,
            kokoro_voice=kokoro_voice,
            kokoro_speed=kokoro_speed,
            tts_max_characters=(
                tts_max_characters
            ),
            docs_dir=BASE_DIR / "docs",
        )