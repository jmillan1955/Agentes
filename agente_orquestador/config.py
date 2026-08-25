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

    context_database_path: Path
    project_name: str
    project_root_path: Path
    git_repository: str | None

    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: float

    whisper_model: str

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
                "Falta TELEGRAM_ALLOWED_USER_ID "
                "en .env"
            )

        try:
            user_id = int(user_id_value)

        except ValueError as error:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_ID debe "
                "ser un número entero"
            ) from error

        database_value = os.getenv(
            "CONTEXT_DATABASE_PATH",
            "data/context.db",
        ).strip()

        if not database_value:
            raise RuntimeError(
                "CONTEXT_DATABASE_PATH no puede "
                "estar vacío"
            )

        database_path = Path(
            database_value
        )

        if not database_path.is_absolute():
            database_path = (
                BASE_DIR / database_path
            )

        project_name = os.getenv(
            "PROJECT_NAME",
            "Agente Orquestador",
        ).strip()

        if not project_name:
            raise RuntimeError(
                "PROJECT_NAME no puede estar vacío"
            )

        git_repository = os.getenv(
            "GIT_REPOSITORY",
            "",
        ).strip()

        ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).strip()

        if not ollama_base_url:
            raise RuntimeError(
                "OLLAMA_BASE_URL no puede "
                "estar vacía"
            )

        ollama_model = os.getenv(
            "OLLAMA_MODEL",
            "qwen3:4b",
        ).strip()

        if not ollama_model:
            raise RuntimeError(
                "OLLAMA_MODEL no puede "
                "estar vacío"
            )

        timeout_value = os.getenv(
            "OLLAMA_TIMEOUT_SECONDS",
            "300",
        ).strip()

        try:
            ollama_timeout_seconds = float(
                timeout_value
            )

        except ValueError as error:
            raise RuntimeError(
                "OLLAMA_TIMEOUT_SECONDS debe "
                "ser un número"
            ) from error

        if ollama_timeout_seconds <= 0:
            raise RuntimeError(
                "OLLAMA_TIMEOUT_SECONDS debe "
                "ser mayor que cero"
            )

        whisper_model = os.getenv(
            "WHISPER_MODEL",
            "small",
        ).strip()

        if not whisper_model:
            raise RuntimeError(
                "WHISPER_MODEL no puede "
                "estar vacío"
            )

        return cls(
            agent_name=os.getenv(
                "AGENT_NAME",
                "Agente Orquestador",
            ).strip(),
            agent_version=os.getenv(
                "AGENT_VERSION",
                "0.1.0",
            ).strip(),
            environment=os.getenv(
                "AGENT_ENVIRONMENT",
                "development",
            ).strip(),
            telegram_bot_token=token,
            telegram_allowed_user_id=user_id,
            context_database_path=(
                database_path.resolve()
            ),
            project_name=project_name,
            project_root_path=(
                BASE_DIR.resolve()
            ),
            git_repository=(
                git_repository or None
            ),
            ollama_base_url=ollama_base_url,
            ollama_model=ollama_model,
            ollama_timeout_seconds=(
                ollama_timeout_seconds
            ),
            whisper_model=whisper_model,
        )