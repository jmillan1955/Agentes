from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Settings:
    agent_name: str
    agent_version: str
    environment: str
    telegram_bot_token: str
    telegram_allowed_user_id: int

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")

        token = os.getenv(
            "TELEGRAM_BOT_TOKEN",
            "",
        ).strip()

        if not token:
            raise RuntimeError(
                "Falta TELEGRAM_BOT_TOKEN en .env"
            )

        user_id_value = os.getenv(
            "TELEGRAM_ALLOWED_USER_ID",
            "",
        ).strip()

        if not user_id_value:
            raise RuntimeError(
                "Falta TELEGRAM_ALLOWED_USER_ID en .env"
            )

        try:
            user_id = int(user_id_value)
        except ValueError as error:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_ID debe "
                "ser un número entero"
            ) from error

        return cls(
            agent_name=os.getenv(
                "AGENT_NAME",
                "Agente Orquestador",
            ),
            agent_version=os.getenv(
                "AGENT_VERSION",
                "0.1.0",
            ),
            environment=os.getenv(
                "AGENT_ENVIRONMENT",
                "development",
            ),
            telegram_bot_token=token,
            telegram_allowed_user_id=user_id,
        )