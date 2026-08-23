from __future__ import annotations

import logging

from app.channels import TelegramChannel
from app.context import (
    ContextDatabase,
    ProjectRepository,
)
from app.orchestrator import Orchestrator
from config import Settings


logging.basicConfig(
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(
    logging.WARNING
)

logging.getLogger("httpcore").setLevel(
    logging.WARNING
)


def main() -> None:
    settings = Settings.load()

    with ContextDatabase(
        settings.context_database_path
    ) as database:
        project_repository = ProjectRepository(
            database
        )

        project = project_repository.save(
            name=settings.project_name,
            root_path=str(
                settings.project_root_path
            ),
            git_repository=(
                settings.git_repository
            ),
        )

        logger.info(
            "Contexto SQLite conectado: %s",
            settings.context_database_path,
        )

        logger.info(
            "Proyecto registrado: id=%s, nombre=%s",
            project.id,
            project.name,
        )

        orchestrator = Orchestrator()

        channel = TelegramChannel(
            token=settings.telegram_bot_token,
            allowed_user_id=(
                settings.telegram_allowed_user_id
            ),
            orchestrator=orchestrator,
        )

        logger.info(
            "Iniciando %s versión %s",
            settings.agent_name,
            settings.agent_version,
        )

        channel.run()


if __name__ == "__main__":
    main()