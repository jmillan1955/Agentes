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
    telegram_allowed_user_ids: tuple[
        int,
        ...,
    ]
    telegram_approver_user_ids: tuple[
        int,
        ...,
    ]

    context_database_path: Path
    project_name: str
    project_root_path: Path
    execution_workspace_root: Path
    git_repository: str | None

    ollama_base_url: str
    ollama_general_model: str
    ollama_coding_model: str
    ollama_timeout_seconds: float

    whisper_model: str

    @property
    def telegram_allowed_user_id(self) -> int:
        """
        Mantiene temporalmente compatibilidad con
        el canal que todavÃ­a espera un solo usuario.
        """
        return self.telegram_allowed_user_ids[0]

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

        user_ids_value = os.getenv(
            "TELEGRAM_ALLOWED_USER_IDS",
            "",
        ).strip()

        if not user_ids_value:
            user_ids_value = os.getenv(
                "TELEGRAM_ALLOWED_USER_ID",
                "",
            ).strip()

        if not user_ids_value:
            raise RuntimeError(
                "Falta TELEGRAM_ALLOWED_USER_IDS "
                "en .env"
            )

        try:
            allowed_user_ids = tuple(
                dict.fromkeys(
                    int(value.strip())
                    for value in (
                        user_ids_value.split(",")
                    )
                    if value.strip()
                )
            )

        except ValueError as error:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_IDS debe "
                "contener numeros enteros "
                "separados por comas"
            ) from error

        if not allowed_user_ids:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_IDS debe "
                "contener al menos un usuario"
            )

        approver_ids_value = os.getenv(
            "TELEGRAM_APPROVER_USER_IDS",
            "",
        ).strip()

        if not approver_ids_value:
            raise RuntimeError(
                "Falta TELEGRAM_APPROVER_USER_IDS "
                "en .env"
            )

        try:
            approver_user_ids = tuple(
                dict.fromkeys(
                    int(value.strip())
                    for value in (
                        approver_ids_value.split(",")
                    )
                    if value.strip()
                )
            )

        except ValueError as error:
            raise RuntimeError(
                "TELEGRAM_APPROVER_USER_IDS debe "
                "contener numeros enteros "
                "separados por comas"
            ) from error

        if not approver_user_ids:
            raise RuntimeError(
                "TELEGRAM_APPROVER_USER_IDS debe "
                "contener al menos un usuario"
            )

        if not set(
            approver_user_ids
        ).issubset(
            allowed_user_ids
        ):
            raise RuntimeError(
                "Todos los aprobadores deben ser "
                "usuarios autorizados"
            )

        database_value = os.getenv(
            "CONTEXT_DATABASE_PATH",
            "data/context.db",
        ).strip()

        if not database_value:
            raise RuntimeError(
                "CONTEXT_DATABASE_PATH no puede "
                "estar vaci­o"
            )

        database_path = Path(
            database_value
        )

        if not database_path.is_absolute():
            database_path = (
                BASE_DIR / database_path
            )

        execution_workspace_value = os.getenv(
            "EXECUTION_WORKSPACE_ROOT",
            "../../Agentes_ejecuciones",
        ).strip()

        if not execution_workspace_value:
            raise RuntimeError(
                "EXECUTION_WORKSPACE_ROOT no "
                "puede estar vacio"
            )

        execution_workspace_root = Path(
            execution_workspace_value
        )

        if (
            not execution_workspace_root
            .is_absolute()
        ):
            execution_workspace_root = (
                BASE_DIR
                / execution_workspace_root
            )

        project_name = os.getenv(
            "PROJECT_NAME",
            "Agente Orquestador",
        ).strip()

        if not project_name:
            raise RuntimeError(
                "PROJECT_NAME no puede estar vacÃ­o"
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
                "estar vacia"
            )

        ollama_general_model = os.getenv(
            "OLLAMA_GENERAL_MODEL",
            "llama3.2:3b",
        ).strip()

        if not ollama_general_model:
            raise RuntimeError(
                "OLLAMA_GENERAL_MODEL no puede "
                "estar vacio"
            )

        ollama_coding_model = os.getenv(
            "OLLAMA_CODING_MODEL",
            "qwen2.5-coder:3b",
        ).strip()

        if not ollama_coding_model:
            raise RuntimeError(
                "OLLAMA_CODING_MODEL no puede "
                "estar vacio"
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
                "ser un numero"
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
                "estar vacio"
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
            telegram_allowed_user_ids=(
                allowed_user_ids
            ),
            telegram_approver_user_ids=(
                approver_user_ids
            ),
            context_database_path=(
                database_path.resolve()
            ),
            project_name=project_name,
            project_root_path=(
                BASE_DIR.resolve()
            ),
            execution_workspace_root=(
                execution_workspace_root.resolve()
            ),
            git_repository=(
                git_repository or None
            ),
            ollama_base_url=ollama_base_url,
            ollama_general_model=(
                ollama_general_model
            ),
            ollama_coding_model=(
                ollama_coding_model
            ),
            ollama_timeout_seconds=(
                ollama_timeout_seconds
            ),
            whisper_model=whisper_model,
        )