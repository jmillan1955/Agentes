from __future__ import annotations

import logging

from app.audio import TranscriptionService
from app.channels import TelegramChannel
from app.context import (
    ContextBuilder,
    ContextDatabase,
    ContextQueryService,
    ContextSearchService,
    DocumentRepository,
    DocumentSynchronizer,
    GitCommitRepository,
    GitCommitSynchronizer,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
    TaskClarificationResponseRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.orchestrator import Orchestrator
from app.planning import PlanningPromptBuilder
from app.planning.clarification_workflow import (
    ClarificationWorkflowService,
)
from app.planning.formatter import (
    PlanningFormatter,
)
from app.planning.service import (
    PlanningService,
)
from app.prompt_builder import PromptBuilder
from app.providers import OllamaProvider
from app.response_generation_service import (
    ResponseGenerationService,
)
from app.routing import (
    ProvisionalTaskHandler,
    RequestClassifier,
)
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

        document_repository = DocumentRepository(
            database
        )

        document_synchronizer = DocumentSynchronizer(
            repository=document_repository,
            project_id=project.id,
            project_root=settings.project_root_path,
        )

        sync_result = (
            document_synchronizer.synchronize()
        )

        logger.info(
            "Documentos sincronizados: "
            "revisados=%s, creados=%s, "
            "actualizados=%s, sin_cambios=%s, "
            "eliminados=%s",
            sync_result.scanned,
            sync_result.created,
            sync_result.updated,
            sync_result.unchanged,
            sync_result.deleted,
        )

        git_commit_repository = (
            GitCommitRepository(database)
        )

        git_commit_synchronizer = (
            GitCommitSynchronizer(
                repository=git_commit_repository,
                project_id=project.id,
                project_root=(
                    settings.project_root_path
                ),
            )
        )

        git_sync_result = (
            git_commit_synchronizer.synchronize()
        )

        logger.info(
            "Commits sincronizados: "
            "revisados=%s, creados=%s, "
            "actualizados=%s, sin_cambios=%s",
            git_sync_result.scanned,
            git_sync_result.created,
            git_sync_result.updated,
            git_sync_result.unchanged,
        )

        session_repository = SessionRepository(
            database
        )

        message_repository = MessageRepository(
            database
        )

        task_repository = TaskRepository(
            database
        )

        clarification_repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        task_plan_repository = (
            TaskPlanRepository(database)
        )

        context_search_service = (
            ContextSearchService(
                document_repository=(
                    document_repository
                ),
                message_repository=(
                    message_repository
                ),
            )
        )

        context_builder = ContextBuilder(
            context_search_service
        )

        general_language_provider = (
            OllamaProvider(
                base_url=(
                    settings.ollama_base_url
                ),
                model=(
                    settings.ollama_general_model
                ),
                timeout_seconds=(
                    settings
                    .ollama_timeout_seconds
                ),
            )
        )

        coding_language_provider = (
            OllamaProvider(
                base_url=(
                    settings.ollama_base_url
                ),
                model=(
                    settings.ollama_coding_model
                ),
                timeout_seconds=(
                    settings
                    .ollama_timeout_seconds
                ),
            )
        )

        logger.info(
            "Modelo para consultas generales: %s",
            settings.ollama_general_model,
        )

        logger.info(
            "Modelo para planificaciÃ³n y cÃ³digo: %s",
            settings.ollama_coding_model,
        )

        response_generation_service = (
            ResponseGenerationService(
                context_builder=context_builder,
                prompt_builder=PromptBuilder(),
                language_provider=(
                    general_language_provider
                ),
            )
        )

        planning_service = PlanningService(
            task_repository=task_repository,
            clarification_repository=(
                clarification_repository
            ),
            plan_repository=(
                task_plan_repository
            ),
            prompt_builder=(
                PlanningPromptBuilder()
            ),
            language_provider=(
                coding_language_provider
            ),
        )

        clarification_workflow_service = (
            ClarificationWorkflowService(
                task_repository=task_repository,
                clarification_repository=(
                    clarification_repository
                ),
                planning_service=(
                    planning_service
                ),
            )
        )

        context_query_service = ContextQueryService(
            database
        )

        orchestrator = Orchestrator(
            project_id=project.id,
            session_repository=(
                session_repository
            ),
            message_repository=(
                message_repository
            ),
            task_repository=(
                task_repository
            ),
            context_query_service=(
                context_query_service
            ),
            context_builder=context_builder,
            response_generation_service=(
                response_generation_service
            ),
            request_classifier=(
                RequestClassifier()
            ),
            task_handler=(
                ProvisionalTaskHandler()
            ),
            clarification_workflow_service=(
                clarification_workflow_service
            ),
            planning_formatter=(
                PlanningFormatter()
            ),
        )

        transcription_service = (
            TranscriptionService(
                model_name=(
                    settings.whisper_model
                ),
                device="cpu",
                compute_type="int8",
                language="es",
            )
        )

        channel = TelegramChannel(
            token=settings.telegram_bot_token,
            allowed_user_id=(
                settings.telegram_allowed_user_id
            ),
            allowed_user_ids=(
                settings.telegram_allowed_user_ids
            ),
            orchestrator=orchestrator,
        )

        logger.info(
            "Iniciando %s versiÃ³n %s",
            settings.agent_name,
            settings.agent_version,
        )

        channel.run()


if __name__ == "__main__":
    main()