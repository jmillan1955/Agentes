from __future__ import annotations

import json
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

    promotion_repository_root: Path
    promotion_allowed_projects: tuple[
        tuple[str, str],
        ...,
    ]

    sandbox_gateway_url: str | None
    sandbox_gateway_token: str | None
    sandbox_gateway_timeout_seconds: float

    ollama_base_url: str
    ollama_general_model: str
    ollama_coding_model: str
    ollama_timeout_seconds: float
    general_provider: str
    planning_provider: str
    comparison_providers: tuple[str, ...]
    openai_api_key: str | None
    openai_general_model: str
    openai_planning_model: str
    openai_general_reasoning_effort: str
    openai_planning_reasoning_effort: str
    openai_timeout_seconds: float
    openai_input_cost_per_million: float
    openai_output_cost_per_million: float
    verification_enabled: bool
    verification_mode: str
    openai_verification_model: str
    openai_verification_reasoning_effort: str
    gemini_api_key: str | None
    gemini_general_model: str
    gemini_timeout_seconds: float

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

        promotion_root_value = os.getenv(
            "PROMOTION_REPOSITORY_ROOT",
            "..",
        ).strip()

        if not promotion_root_value:
            raise RuntimeError(
                "PROMOTION_REPOSITORY_ROOT no "
                "puede estar vacio"
            )

        promotion_repository_root = Path(
            promotion_root_value
        )

        if (
            not promotion_repository_root
            .is_absolute()
        ):
            promotion_repository_root = (
                BASE_DIR
                / promotion_repository_root
            )

        promotion_projects_value = os.getenv(
            "PROMOTION_ALLOWED_PROJECTS",
            "{}",
        ).strip()

        if not promotion_projects_value:
            raise RuntimeError(
                "PROMOTION_ALLOWED_PROJECTS debe "
                "ser un objeto JSON"
            )

        try:
            promotion_projects_data = (
                json.loads(
                    promotion_projects_value
                )
            )

        except json.JSONDecodeError as error:
            raise RuntimeError(
                "PROMOTION_ALLOWED_PROJECTS debe "
                "ser un objeto JSON valido"
            ) from error

        if not isinstance(
            promotion_projects_data,
            dict,
        ):
            raise RuntimeError(
                "PROMOTION_ALLOWED_PROJECTS debe "
                "ser un objeto JSON"
            )

        promotion_allowed_projects: list[
            tuple[str, str]
        ] = []

        for (
            target_project_name,
            target_subdirectory,
        ) in promotion_projects_data.items():
            if (
                not isinstance(
                    target_project_name,
                    str,
                )
                or not isinstance(
                    target_subdirectory,
                    str,
                )
            ):
                raise RuntimeError(
                    "PROMOTION_ALLOWED_PROJECTS "
                    "debe relacionar nombres y "
                    "subdirectorios de texto"
                )

            normalized_name = (
                target_project_name.strip()
            )
            normalized_subdirectory = (
                target_subdirectory.strip()
            )

            if (
                not normalized_name
                or not normalized_subdirectory
            ):
                raise RuntimeError(
                    "PROMOTION_ALLOWED_PROJECTS "
                    "no admite valores vacios"
                )

            promotion_allowed_projects.append(
                (
                    normalized_name,
                    normalized_subdirectory,
                )
            )

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

        supported_providers = {"ollama", "openai", "gemini"}
        general_provider = os.getenv("GENERAL_PROVIDER", "ollama").strip().lower()
        planning_provider = os.getenv("PLANNING_PROVIDER", "ollama").strip().lower()
        comparison_providers = tuple(dict.fromkeys(
            item.strip().lower()
            for item in os.getenv("COMPARISON_PROVIDERS", "ollama").split(",")
            if item.strip()
        ))
        selected = {general_provider, planning_provider, *comparison_providers}
        unknown = selected - supported_providers
        if unknown:
            raise RuntimeError("Proveedor no soportado: " + ", ".join(sorted(unknown)))

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or None
        if "openai" in selected and not openai_api_key:
            raise RuntimeError("Falta OPENAI_API_KEY para usar OpenAI")
        if "gemini" in selected and not gemini_api_key:
            raise RuntimeError("Falta GEMINI_API_KEY para usar Gemini")

        def number(name: str, default: str, allow_zero: bool = False) -> float:
            try:
                value = float(os.getenv(name, default).strip())
            except ValueError as error:
                raise RuntimeError(f"{name} debe ser un numero") from error
            if value < 0 or (value == 0 and not allow_zero):
                raise RuntimeError(f"{name} debe ser positivo")
            return value

        openai_general_model = os.getenv("OPENAI_GENERAL_MODEL", "gpt-5").strip()
        openai_planning_model = os.getenv("OPENAI_PLANNING_MODEL", "gpt-5").strip()

        def reasoning_effort(name: str, default: str) -> str:
            value = os.getenv(name, default).strip().lower()
            supported = {"minimal", "low", "medium", "high"}
            if value not in supported:
                raise RuntimeError(
                    f"{name} debe ser uno de: "
                    + ", ".join(sorted(supported))
                )
            return value

        openai_general_reasoning_effort = reasoning_effort(
            "OPENAI_GENERAL_REASONING_EFFORT", "minimal"
        )
        openai_planning_reasoning_effort = reasoning_effort(
            "OPENAI_PLANNING_REASONING_EFFORT", "low"
        )
        openai_timeout_seconds = number("OPENAI_TIMEOUT_SECONDS", "120")
        openai_input_cost_per_million = number(
            "OPENAI_INPUT_COST_PER_MILLION", "1.25", allow_zero=True
        )
        openai_output_cost_per_million = number(
            "OPENAI_OUTPUT_COST_PER_MILLION", "10", allow_zero=True
        )

        verification_enabled_value = os.getenv(
            "VERIFICATION_ENABLED", "false"
        ).strip().lower()
        if verification_enabled_value not in {
            "true", "false"
        }:
            raise RuntimeError(
                "VERIFICATION_ENABLED debe ser "
                "true o false"
            )
        verification_enabled = (
            verification_enabled_value == "true"
        )
        verification_mode = os.getenv(
            "VERIFICATION_MODE", "automatic"
        ).strip().lower()
        if verification_mode not in {
            "automatic", "on_demand"
        }:
            raise RuntimeError(
                "VERIFICATION_MODE debe ser "
                "automatic o on_demand"
            )
        openai_verification_model = os.getenv(
            "OPENAI_VERIFICATION_MODEL",
            openai_general_model,
        ).strip()
        openai_verification_reasoning_effort = (
            reasoning_effort(
                "OPENAI_VERIFICATION_REASONING_EFFORT",
                "low",
            )
        )

        gemini_general_model = os.getenv(
            "GEMINI_GENERAL_MODEL", "gemini-2.5-flash-lite"
        ).strip()
        gemini_timeout_seconds = number("GEMINI_TIMEOUT_SECONDS", "120")

        sandbox_gateway_url_value = os.getenv(
            "SANDBOX_GATEWAY_URL",
            "",
        ).strip()

        sandbox_gateway_token_value = os.getenv(
            "SANDBOX_GATEWAY_TOKEN",
            "",
        ).strip()

        if bool(
            sandbox_gateway_url_value
        ) != bool(
            sandbox_gateway_token_value
        ):
            raise RuntimeError(
                "SANDBOX_GATEWAY_URL y "
                "SANDBOX_GATEWAY_TOKEN deben "
                "configurarse juntos"
            )

        if (
            sandbox_gateway_token_value
            and len(
                sandbox_gateway_token_value
            ) < 32
        ):
            raise RuntimeError(
                "SANDBOX_GATEWAY_TOKEN debe "
                "tener al menos 32 caracteres"
            )

        sandbox_gateway_timeout_value = (
            os.getenv(
                "SANDBOX_GATEWAY_TIMEOUT_SECONDS",
                "150",
            ).strip()
        )

        try:
            sandbox_gateway_timeout_seconds = (
                float(
                    sandbox_gateway_timeout_value
                )
            )

        except ValueError as error:
            raise RuntimeError(
                "SANDBOX_GATEWAY_TIMEOUT_SECONDS "
                "debe ser un numero positivo"
            ) from error

        if (
            sandbox_gateway_timeout_seconds
            <= 0
        ):
            raise RuntimeError(
                "SANDBOX_GATEWAY_TIMEOUT_SECONDS "
                "debe ser un numero positivo"
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
            promotion_repository_root=(
                promotion_repository_root
                .resolve()
            ),
            promotion_allowed_projects=(
                tuple(
                    promotion_allowed_projects
                )
            ),
            sandbox_gateway_url=(
                sandbox_gateway_url_value
                or None
            ),
            sandbox_gateway_token=(
                sandbox_gateway_token_value
                or None
            ),
            sandbox_gateway_timeout_seconds=(
                sandbox_gateway_timeout_seconds
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
            general_provider=general_provider,
            planning_provider=planning_provider,
            comparison_providers=comparison_providers,
            openai_api_key=openai_api_key,
            openai_general_model=openai_general_model,
            openai_planning_model=openai_planning_model,
            openai_general_reasoning_effort=openai_general_reasoning_effort,
            openai_planning_reasoning_effort=openai_planning_reasoning_effort,
            openai_timeout_seconds=openai_timeout_seconds,
            openai_input_cost_per_million=openai_input_cost_per_million,
            openai_output_cost_per_million=openai_output_cost_per_million,
            verification_enabled=verification_enabled,
            verification_mode=verification_mode,
            openai_verification_model=openai_verification_model,
            openai_verification_reasoning_effort=(
                openai_verification_reasoning_effort
            ),
            gemini_api_key=gemini_api_key,
            gemini_general_model=gemini_general_model,
            gemini_timeout_seconds=gemini_timeout_seconds,
            whisper_model=whisper_model,
        )
