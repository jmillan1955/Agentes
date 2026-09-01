from __future__ import annotations

import logging

from app.approvals.formatter import (
    ApprovalFormatter,
)
from app.approvals.service import (
    ApprovalService,
)

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
    TaskApprovalRepository,
    TaskExecutionRepository,
)
from app.orchestrator import Orchestrator
from app.execution.factory import (
    create_execution_runtime,
)
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
from app.providers import (GeminiProvider, LanguageProvider, OllamaProvider,
                           OpenAIProvider, ProviderComparisonService)
from app.response_generation_service import (
    ResponseGenerationService,
)
from app.verification import VerificationPolicy
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


def create_language_provider(
    settings: Settings, provider_name: str, *, planning: bool = False
) -> LanguageProvider:
    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=(settings.ollama_coding_model if planning
                   else settings.ollama_general_model),
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    if provider_name == "openai":
        if settings.openai_api_key is None:
            raise RuntimeError("Falta OPENAI_API_KEY")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=(settings.openai_planning_model if planning
                   else settings.openai_general_model),
            timeout_seconds=settings.openai_timeout_seconds,
            input_cost_per_million=settings.openai_input_cost_per_million,
            output_cost_per_million=settings.openai_output_cost_per_million,
            reasoning_effort=(settings.openai_planning_reasoning_effort
                              if planning else
                              settings.openai_general_reasoning_effort),
        )
    if provider_name == "gemini":
        if settings.gemini_api_key is None:
            raise RuntimeError("Falta GEMINI_API_KEY")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_general_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
    raise RuntimeError(f"Proveedor no soportado: {provider_name}")


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

        task_approval_repository = (
            TaskApprovalRepository(database)
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

        general_language_provider = create_language_provider(
            settings, settings.general_provider
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
            "Proveedor para consultas generales: %s",
            settings.general_provider,
        )

        logger.info(
            "Proveedor para planificacion: %s",
            settings.planning_provider,
        )

        planning_language_provider = create_language_provider(
            settings, settings.planning_provider, planning=True
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

        verification_response_service = None
        verification_policy = None
        if settings.verification_enabled:
            if settings.openai_api_key is None:
                raise RuntimeError(
                    "Falta OPENAI_API_KEY para "
                    "activar la verificación"
                )
            verification_provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=(
                    settings
                    .openai_verification_model
                ),
                timeout_seconds=(
                    settings.openai_timeout_seconds
                ),
                input_cost_per_million=(
                    settings
                    .openai_input_cost_per_million
                ),
                output_cost_per_million=(
                    settings
                    .openai_output_cost_per_million
                ),
                reasoning_effort=(
                    settings
                    .openai_verification_reasoning_effort
                ),
                web_search_enabled=True,
            )
            verification_response_service = (
                ResponseGenerationService(
                    context_builder=context_builder,
                    prompt_builder=PromptBuilder(),
                    language_provider=(
                        verification_provider
                    ),
                )
            )
            verification_policy = VerificationPolicy(
                settings.verification_mode
            )

        comparison_service = ProviderComparisonService({
            name: create_language_provider(settings, name)
            for name in settings.comparison_providers
        })

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
                planning_language_provider
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

        approval_service = ApprovalService(
            task_repository=task_repository,
            plan_repository=(
                task_plan_repository
            ),
            approval_repository=(
                task_approval_repository
            ),
            execution_repository=(
                TaskExecutionRepository(
                    database
                )
            ),
            approver_user_ids=(
                settings
                .telegram_approver_user_ids
            ),
        )

        context_query_service = ContextQueryService(
            database
        )
        execution_runtime = (
            create_execution_runtime(
                database=database,
                language_provider=(
                    coding_language_provider
                ),
                execution_workspace_root=(
                    settings
                    .execution_workspace_root
                ),
                protected_project_root=(
                    settings.project_root_path
                ),
                sandbox_gateway_url=(
                    settings.sandbox_gateway_url
                ),
                sandbox_gateway_token=(
                    settings.sandbox_gateway_token
                ),
                sandbox_gateway_timeout_seconds=(
                    settings
                    .sandbox_gateway_timeout_seconds
                ),
                promotion_repository_root=(
                    settings
                    .promotion_repository_root
                ),
                promotion_allowed_projects=(
                    settings
                    .promotion_allowed_projects
                ),
            )
        )

        logger.info(
            "Subsistema de ejecucion preparado; "
            "sandbox_remoto=%s",
            execution_runtime.sandbox_enabled,
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
            task_plan_repository=(
                task_plan_repository
            ),
            context_query_service=(
                context_query_service
            ),
            context_builder=context_builder,
            response_generation_service=(
                response_generation_service
            ),
            provider_comparison_service=comparison_service,
            verification_response_service=(
                verification_response_service
            ),
            verification_policy=verification_policy,
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
            approval_service=(
                approval_service
            ),
            approval_formatter=(
                ApprovalFormatter()
            ),
            execution_preparation_service=(
                execution_runtime
                .preparation_service
            ),
            execution_query_service=(
                execution_runtime.query_service
            ),
            execution_manifest_service=(
                execution_runtime.manifest_service
            ),
            execution_action_generator=(
                execution_runtime
                .action_generator
            ),
            execution_start_service=(
                execution_runtime
                .start_service
            ),
            execution_runner=(
                execution_runtime.runner
            ),
            promotion_preparation_service=(
                execution_runtime
                .promotion_preparation_service
            ),
            promotion_query_service=(
                execution_runtime
                .promotion_query_service
            ),
            promotion_finalization_service=(
                execution_runtime
                .promotion_finalization_service
            ),
            promotion_target_resolver=(
                execution_runtime
                .promotion_target_resolver
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
