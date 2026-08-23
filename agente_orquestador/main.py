from __future__ import annotations

import logging

from app.channels import TelegramChannel
from app.orchestrator import Orchestrator
from config import Settings


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
logger = logging.getLogger(__name__)

def main() -> None:
    settings = Settings.load()
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