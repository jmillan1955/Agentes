from __future__ import annotations

from app.approvals.formatter import (
    ApprovalFormatter,
)
from app.approvals.service import (
    ApprovalError,
    ApprovalService,
)

from app.context import (
    ContextBuilder,
    ContextQueryService,
    ContextSummary,
    MessageRepository,
    SessionRepository,
    TaskRepository,
    TaskPlanRepository,
)
from app.execution.runner import (
    ExecutionRunError,
    ExecutionRunner,
)
from app.execution.service import (
    ExecutionPreparationError,
    ExecutionPreparationService,
)
from app.execution.action_generator import (
    ExecutionActionGenerationError,
    ExecutionActionGenerator,
)
from app.execution.timing import (
    elapsed_seconds_between,
    format_elapsed_seconds,
)
from app.models import (
    ContentType,
    IncomingMessage,
    OutgoingMessage,
)
from app.planning.clarification_workflow import (
    ClarificationWorkflowService,
)
from app.planning.formatter import (
    PlanningFormatter,
)
from app.planning.service import (
    PlanningGenerationError,
)
from app.providers import (
    LanguageProviderError,
    ProviderComparisonService,
)
from app.response_generation_service import (
    ResponseGenerationService,
)
from app.routing import (
    ProvisionalTaskHandler,
    RequestClassifier,
    RequestKind,
)
from app.tasks import (
    TaskClarificationAnalyzer,
    TaskStatus,
)
from app.execution.query import (
    ExecutionQueryError,
    ExecutionQueryService,
)
from app.execution.manifest_service import (
    ExecutionManifestConfirmationError,
    ExecutionManifestService,
)
from app.execution.start_service import (
    ExecutionStartError,
    ExecutionStartService,
)
from app.execution.promotion_preparation import (
    PromotionPreparationError,
    PromotionPreparationService,
)
from app.execution.audited_promotion_finalization import (
    AuditedPromotionFinalizationError,
    AuditedPromotionFinalizationService,
)
from app.execution.promotion_target import (
    PromotionTargetResolutionError,
    PromotionTargetResolver,
)
from app.execution.promotion_query import (
    PromotionQueryError,
    PromotionQueryService,
)

class Orchestrator:
    def __init__(
        self,
        project_id: int,
        session_repository: SessionRepository,
        message_repository: MessageRepository,
        task_repository: TaskRepository,
        context_query_service: ContextQueryService,
        context_builder: ContextBuilder,
        response_generation_service: (
            ResponseGenerationService
        ),
        provider_comparison_service: ProviderComparisonService | None = None,
        task_plan_repository: (
            TaskPlanRepository | None
        ) = None,
        request_classifier: (
            RequestClassifier | None
        ) = None,
        task_handler: (
            ProvisionalTaskHandler | None
        ) = None,
        clarification_analyzer: (
            TaskClarificationAnalyzer | None
        ) = None,
        clarification_workflow_service: (
            ClarificationWorkflowService | None
        ) = None,
        planning_formatter: (
            PlanningFormatter | None
        ) = None,
        approval_service: (
            ApprovalService | None
        ) = None,
        approval_formatter: (
            ApprovalFormatter | None
        ) = None,
        execution_preparation_service: (
            ExecutionPreparationService | None
        ) = None,
        execution_query_service: (
            ExecutionQueryService | None
        ) = None,
        execution_manifest_service: (
            ExecutionManifestService | None
        ) = None,
        execution_action_generator: (
            ExecutionActionGenerator | None
        ) = None,
        execution_start_service: (
            ExecutionStartService | None
        ) = None,
        execution_runner: (
            ExecutionRunner | None
        ) = None,
        promotion_preparation_service: (
            PromotionPreparationService | None
        ) = None,
        promotion_query_service: (
            PromotionQueryService | None
        ) = None,
        promotion_finalization_service: (
            AuditedPromotionFinalizationService
            | None
        ) = None,
        promotion_target_resolver: (
            PromotionTargetResolver | None
        ) = None,
    ) -> None:
        self._project_id = project_id
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

        self._context_query_service = context_query_service
        self._context_builder = context_builder
        self._response_generation_service = (
            response_generation_service
        )
        self._provider_comparison_service = provider_comparison_service
        self._task_plan_repository = task_plan_repository
        self._request_classifier = (
            request_classifier
            or RequestClassifier()
        )
        self._task_handler = (
            task_handler
            or ProvisionalTaskHandler()
        )
        self._clarification_analyzer = (
            clarification_analyzer
            or TaskClarificationAnalyzer()
        )
        self._clarification_workflow_service = (
            clarification_workflow_service
        )
        self._planning_formatter = (
            planning_formatter
            or PlanningFormatter()
        )
        self._approval_service = approval_service
        self._approval_formatter = (
            approval_formatter
            or ApprovalFormatter()
        )
        self._execution_preparation_service = (
            execution_preparation_service
        )
        self._execution_query_service = (
            execution_query_service
        )
        self._execution_manifest_service = (
            execution_manifest_service
        )
        self._execution_action_generator = (
            execution_action_generator
        )
        self._execution_start_service = (
            execution_start_service
        )
        self._execution_runner = (
            execution_runner
        )
        self._promotion_preparation_service = (
            promotion_preparation_service
        )
        self._promotion_query_service = (
            promotion_query_service
        )
        self._promotion_finalization_service = (
            promotion_finalization_service
        )
        self._promotion_target_resolver = (
            promotion_target_resolver
        )

    def process(
        self,
        message: IncomingMessage,
    ) -> OutgoingMessage:
        session = (
            self._session_repository
            .get_or_create_active(
                project_id=self._project_id,
                channel=message.channel.value,
                user_id=message.user_id,
                conversation_id=(
                    message.conversation_id
                ),
            )
        )

        self._message_repository.save_incoming(
            session_id=session.id,
            message=message,
        )

        outgoing = self._create_response(
            message=message,
            session_id=session.id,
        )

        self._message_repository.save_outgoing(
            session_id=session.id,
            message=outgoing,
        )

        return outgoing

    def _create_response(
        self,
        message: IncomingMessage,
        session_id: int,
    ) -> OutgoingMessage:
        metadata: dict[str, object] = {
            "processor": "orchestrator",
            "session_id": session_id,
        }

        decision = None

        if message.content_type in (
            ContentType.TEXT,
            ContentType.COMMAND,
        ):
            decision = (
                self._request_classifier.classify(
                    message.text or ""
                )
            )

            metadata.update(
                {
                    "routing_kind": (
                        decision.kind.value
                    ),
                    "routing_confidence": (
                        decision.confidence
                    ),
                    "routing_summary": (
                        decision.summary
                    ),
                    "routing_requires_clarification": (
                        decision
                        .requires_clarification
                    ),
                }
            )

            if decision.project_name is not None:
                metadata["routing_project"] = (
                    decision.project_name
                )

            if decision.missing_information:
                metadata[
                    "routing_missing_information"
                ] = decision.missing_information

        if message.content_type == ContentType.COMMAND:
            (
                response_text,
                command_metadata,
            ) = self._process_command(
                text=message.text,
                message_id=message.message_id,
                session_id=session_id,
                user_id=message.user_id,
                channel=message.channel.value,
            )

            metadata.update(command_metadata)

        elif message.content_type == ContentType.TEXT:
            if (
                decision is not None
                and decision.kind
                == RequestKind.TASK
            ):
                task = self._process_task(
                    decision=decision,
                    message=message,
                    session_id=session_id,
                )

                task_result = (
                    self._task_handler.handle(
                        decision=decision,
                        task=task,
                    )
                )

                response_text = "\n".join(
                    [
                        "TAREA REGISTRADA",
                        "",
                        (
                            "Identificador: "
                            f"#{task.id}"
                        ),
                        "",
                        task_result.text,
                    ]
                )

                metadata.update(
                    {
                        "route": "task_handler",
                        "task_id": task.id,
                        "task_status": (
                            task.status.value
                        ),
                        "task_project": (
                            task.target_project_name
                        ),
                        "task_missing_information": (
                            task.missing_information
                        ),
                    }
                )

            else:
                (
                    response_text,
                    language_metadata,
                ) = self._generate_language_response(
                    message=message,
                    include_context=(
                        decision is not None
                        and decision.kind
                        == RequestKind.PROJECT_QUERY
                    ),
                )

                metadata.update(
                    language_metadata
                )

        else:
            response_text = (
                "He recibido un contenido de tipo "
                f"'{message.content_type.value}'. "
                "Todavía solamente proceso texto."
            )

        return OutgoingMessage(
            channel=message.channel,
            conversation_id=(
                message.conversation_id
            ),
            content_type=ContentType.TEXT,
            correlation_id=message.message_id,
            text=response_text,
            metadata=metadata,
        )

    def _process_task(
        self,
        decision,
        message: IncomingMessage,
        session_id: int,
    ):
        task = self._task_repository.create(
            project_id=self._project_id,
            session_id=session_id,
            source_message_id=(
                message.message_id
            ),
            title=decision.summary,
            description=decision.summary,
            target_project_name=(
                decision.project_name
            ),
        )

        if (
            task.status
            == TaskStatus.PENDING_PLANNING
            and not task.missing_information
            and not task.plan
        ):
            missing_information = (
                self._clarification_analyzer
                .analyze(task)
            )

            if missing_information:
                task = (
                    self._task_repository
                    .set_missing_information(
                        task_id=task.id,
                        missing_information=(
                            missing_information
                        ),
                    )
                )

        return task

    def _generate_language_response(
        self,
        message: IncomingMessage,
        include_context: bool,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        try:
            answer = (
                self._response_generation_service
                .generate(
                    project_id=self._project_id,
                    query=message.text or "",
                    current_message_id=(
                        message.message_id
                    ),
                    include_context=(
                        include_context
                    ),
                    response_style=(
                        message.metadata.get(
                            "response_style"
                        )
                    ),
                )            )

            metadata = {
                "route": "language_provider",
                "model": answer.model,
                "provider": answer.provider,
                "input_tokens": answer.input_tokens,
                "output_tokens": answer.output_tokens,
                "estimated_cost_usd": (
                    answer.estimated_cost_usd
                ),
                "elapsed_seconds": (
                    answer.elapsed_seconds
                ),
                "context_included": (
                    include_context
                ),
                "response_style": (
                    message.metadata.get(
                        "response_style",
                        "default",
                    )
                ),
                "context_documents": (
                    answer.document_paths
                ),
                "context_messages": (
                    answer.message_ids
                ),
                "context_characters": (
                    answer.context_characters
                ),
                "context_truncated": (
                    answer.context_truncated
                ),
            }

            return answer.text, metadata

        except LanguageProviderError as error:
            response_text = (
                "No se ha podido generar "
                "la respuesta.\n\n"
                f"{error}"
            )

            metadata = {
                "route": "language_provider",
                "error": type(error).__name__,
                "error_message": str(error),
                "context_included": (
                    include_context
                ),
            }

            return response_text, metadata

    def _process_command(
        self,
        text: str | None,
        message_id: str,
        session_id: int,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        command_text = (text or "").strip()

        parts = command_text.split(
            maxsplit=1
        )

        command = (
            parts[0]
            .split("@", maxsplit=1)[0]
            .lower()
            if parts
            else ""
        )

        arguments = (
            parts[1].strip()
            if len(parts) > 1
            else ""
        )
        if command == "/generar_manifiesto":
            return (
                self
                ._process_generate_manifest_command(
                    arguments
                )
            )
        if command == "/ver_manifiesto":
            return (
                self
                ._process_view_manifest_command(
                    arguments
                )
            )
        if command == "/confirmar_manifiesto":
            return (
                self
                ._process_confirm_manifest_command(
                    arguments=arguments,
                    message_id=message_id,
                    user_id=user_id,
                    channel=channel,
                )
            )
        if command == "/iniciar_ejecucion":
            return (
                self
                ._process_start_execution_command(
                    arguments=arguments,
                    user_id=user_id,
                )
            )
        if command == "/reanudar_ejecucion":
            return (
                self
                ._process_start_execution_command(
                    arguments=arguments,
                    user_id=user_id,
                    resume=True,
                )
            )
        if command == "/ver_ejecucion":
            return (
                self
                ._process_view_execution_command(
                    arguments
                )
            )
        if command == "/ver_promocion":
            return (
                self
                ._process_view_promotion_command(
                    arguments
                )
            )
        if command == "/ver_plan":
            return self._process_view_plan_command(
                arguments
            )
        if command == "/preparar_promocion":
            return (
                self
                ._process_prepare_promotion_command(
                    arguments=arguments,
                    message_id=message_id,
                    user_id=user_id,
                    channel=channel,
                )
            )
        if command == "/confirmar_promocion":
            return (
                self
                ._process_confirm_promotion_command(
                    arguments=arguments,
                    message_id=message_id,
                    user_id=user_id,
                    channel=channel,
                )
            )
        if command == "/preparar_ejecucion":
            return (
                self
                ._process_prepare_execution_command(
                    arguments=arguments,
                    message_id=message_id,
                    user_id=user_id,
                    channel=channel,
                )
            )
        if command == "/aprobar":
            return self._process_approve_command(
                arguments=arguments,
                message_id=message_id,
                user_id=user_id,
                channel=channel,
            )

        if command == "/cancelar_ejecucion":
            return (
                self
                ._process_cancel_execution_command(
                    arguments=arguments,
                    user_id=user_id,
                )
            )

        if command == "/cancelar":
            return self._process_cancel_command(
                arguments=arguments,
                user_id=user_id,
            )

        if command == "/responder":
            return self._process_respond_command(
                arguments=arguments,
                message_id=message_id,
                session_id=session_id,
            )

        if command == "/clasificar":
            return (
                self._process_classify_command(
                    arguments
                ),
                {},
            )

        if command == "/comparar_modelos":
            if not arguments:
                return ("Debes indicar una pregunta.", {"route": "provider_comparison"})
            if self._provider_comparison_service is None:
                return ("La comparacion no esta configurada.", {"route": "provider_comparison"})
            text, models = self._provider_comparison_service.compare(arguments)
            return (text, {"route": "provider_comparison", "models": models})

        if command == "/contexto":
            summary = (
                self._context_query_service
                .get_summary(self._project_id)
            )

            return (
                self._format_context(summary),
                {},
            )

        if command == "/buscar":
            if not arguments:
                return (
                    (
                        "Debes indicar qué quieres "
                        "buscar.\n\n"
                        "Ejemplo:\n"
                        "/buscar integración Telegram"
                    ),
                    {},
                )

            context = self._context_builder.build(
                project_id=self._project_id,
                query=arguments,
                current_message_id=message_id,
                maximum_characters=3900,
            )

            return (
                context.text,
                {},
            )

        return (
            (
                "/preparar_promocion <tarea_id>\n"
                "/ver_promocion <promocion_id>\n"
                "/confirmar_promocion <promocion_id>\n"
                "Comando no reconocido.\n\n"
                "Comandos disponibles:\n"
                "/generar_manifiesto "
                "<tarea_id>\n"
                "/contexto\n"
                "/buscar <consulta>\n"
                "/clasificar <petición>\n"
                "/responder <tarea_id> "
                "<aclaraciones>\n"
                "/ver_plan <tarea_id>\n"
                "/ver_ejecucion "
                "/ver_manifiesto "
                "<tarea_id>\n"
                "/confirmar_manifiesto "
                "<tarea_id> <hash> CONFIRMAR "
                "[DESTRUCTIVO]\n"
                "/iniciar_ejecucion "
                "<tarea_id>\n"
                "/aprobar <tarea_id>\n"
                "/preparar_ejecucion "
                "<tarea_id>\n"
                "/cancelar <tarea_id>\n"
                "/cancelar_ejecucion "
                "<tarea_id>\n"
                "/simple <pregunta>"
                "\n/comparar_modelos <pregunta>"
            ),
            {},
        )

    def _process_view_plan_command(
        self,
        arguments: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuyo "
                    "plan quieres consultar.\n\n"
                    "Ejemplo:\n"
                    "/ver_plan 3"
                ),
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/ver_plan 3"
                ),
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                ),
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "invalid_task_id"
                    ),
                },
            )

        task = self._task_repository.get_by_id(
            task_id
        )

        if (
            task is None
            or task.project_id
            != self._project_id
        ):
            return (
                f"No existe la tarea #{task_id}",
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "task_not_found"
                    ),
                    "task_id": task_id,
                },
            )

        if self._task_plan_repository is None:
            return (
                (
                    "El servicio de consulta de "
                    "planes no esta disponible."
                ),
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        plan = (
            self._task_plan_repository
            .get_latest(task_id)
        )

        if plan is None:
            return (
                (
                    f"La tarea #{task_id} "
                    "todavia no tiene un plan."
                ),
                {
                    "route": "plan_query",
                    "plan_query_error": (
                        "plan_not_found"
                    ),
                    "task_id": task_id,
                },
            )

        text = self._planning_formatter.format(
            plan=plan,
            task=task,
        )

        return (
            text,
            {
                "route": "plan_query",
                "task_id": task.id,
                "task_status": (
                    task.status.value
                ),
                "plan_id": plan.id,
                "plan_version": plan.version,
                "plan_status": (
                    plan.status.value
                ),
            },
        )

    def _process_approve_command(
        self,
        arguments: str,
        message_id: str,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea que "
                    "quieres aprobar.\n\n"
                    "Ejemplo:\n"
                    "/aprobar 3"
                ),
                {
                    "route": "approval_service",
                    "approval_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/aprobar 3"
                ),
                {
                    "route": "approval_service",
                    "approval_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/aprobar 3"
                ),
                {
                    "route": "approval_service",
                    "approval_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if self._approval_service is None:
            return (
                (
                    "El servicio de aprobacion "
                    "no esta disponible."
                ),
                {
                    "route": "approval_service",
                    "approval_error": (
                        "service_unavailable"
                    ),
                },
            )

        try:
            result = (
                self._approval_service.approve(
                    task_id=task_id,
                    authorized_user_id=user_id,
                    authorization_message_id=(
                        message_id
                    ),
                    channel=channel,
                )
            )

        except ApprovalError as error:
            return (
                str(error),
                {
                    "route": "approval_service",
                    "approval_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        text = self._approval_formatter.format(
            result
        )

        return (
            text,
            {
                "route": "approval_service",
                "task_id": result.task.id,
                "task_status": (
                    result.task.status.value
                ),
                "plan_id": result.plan.id,
                "plan_version": (
                    result.plan.version
                ),
                "approval_id": (
                    result.approval.id
                ),
                "authorized_user_id": (
                    result.approval
                    .authorized_user_id
                ),
                "already_approved": (
                    result.already_approved
                ),
            },
        )

    def _process_start_execution_command(
        self,
        arguments: str,
        user_id: str,
        resume: bool = False,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if resume:
            route = "execution_resume_service"
            operation = "reanudar"
            command_example = (
                "/reanudar_ejecucion 4"
            )
        else:
            route = "execution_start_service"
            operation = "iniciar"
            command_example = (
                "/iniciar_ejecucion 4"
            )

        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuya "
                    f"ejecucion quieres {operation}."
                    "\n\nEjemplo:\n"
                    f"{command_example}"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    f"{command_example}"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    f"{command_example}"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if self._execution_start_service is None:
            return (
                (
                    "El servicio de "
                    f"{operation} ejecuciones "
                    "no esta disponible."
                ),
                {
                    "route": route,
                    "execution_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            if resume:
                result = (
                    self._execution_start_service
                    .resume(
                        task_id=task_id,
                        requested_by_user_id=(
                            user_id
                        ),
                    )
                )
            else:
                result = (
                    self._execution_start_service
                    .start(
                        task_id=task_id,
                        requested_by_user_id=(
                            user_id
                        ),
                    )
                )

        except ExecutionRunError as error:
            sandbox_result = (
                error.sandbox_result
            )

            if sandbox_result is None:
                return (
                    (
                        "EJECUCION FALLIDA\n\n"
                        f"{error}\n\n"
                        "Consulta el detalle con:\n"
                        f"/ver_ejecucion {task_id}"
                    ),
                    {
                        "route": route,
                        "execution_error": (
                            type(error).__name__
                        ),
                        "task_id": task_id,
                    },
                )

            stdout_summary = (
                sandbox_result.stdout_text[
                    -1200:
                ]
            )
            stderr_summary = (
                sandbox_result.stderr_text[
                    -1200:
                ]
            )

            lines = [
                "EJECUCION FALLIDA",
                "",
                str(error),
                (
                    "Codigo de salida: "
                    f"{sandbox_result.exit_code}"
                ),
                (
                    "Tiempo: "
                    f"{sandbox_result.duration_seconds:.2f} "
                    "segundos"
                ),
            ]

            if stdout_summary:
                lines.extend(
                    (
                        "",
                        "SALIDA DE PYTEST",
                        stdout_summary,
                    )
                )

            if stderr_summary:
                lines.extend(
                    (
                        "",
                        "ERRORES DE PYTEST",
                        stderr_summary,
                    )
                )

            lines.extend(
                (
                    "",
                    "Consulta la auditoria con:",
                    f"/ver_ejecucion {task_id}",
                )
            )

            return (
                "\n".join(lines),
                {
                    "route": route,
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                    "exit_code": (
                        sandbox_result.exit_code
                    ),
                    "timed_out": (
                        sandbox_result.timed_out
                    ),
                    "duration_seconds": (
                        sandbox_result
                        .duration_seconds
                    ),
                },
            )

        except ExecutionStartError as error:
            return (
                str(error),
                {
                    "route": route,
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        run_result = result.run_result
        execution = run_result.execution
        attempt = run_result.attempt
        manifest = result.manifest

        execution_elapsed_seconds = (
            elapsed_seconds_between(
                started_at=execution.started_at,
                finished_at=execution.finished_at,
            )
        )

        step_elapsed_seconds = tuple(
            {
                "step_number": step.step_number,
                "elapsed_seconds": (
                    elapsed_seconds_between(
                        started_at=step.started_at,
                        finished_at=step.finished_at,
                    )
                ),
            }
            for step in run_result.steps
        )

        step_lines = [
            (
                f"Paso {step.step_number}: "
                f"{step.name} "
                f"[{step.status.value}] - "
                + format_elapsed_seconds(
                    started_at=step.started_at,
                    finished_at=step.finished_at,
                )
            )
            for step in run_result.steps
        ]

        lines = [
            "EJECUCION COMPLETADA",
            "",
            f"Tarea: #{execution.task_id}",
            f"Ejecucion: #{execution.id}",
            f"Manifiesto: #{manifest.id}",
            (
                "Version del manifiesto: "
                f"{manifest.version}"
            ),
            (
                "Intento: "
                f"#{attempt.attempt_number}"
            ),
            (
                "Estado: "
                f"{execution.status.value}"
            ),
            (
                "Acciones ejecutadas: "
                f"{len(result.actions)}"
            ),
            (
                "Tiempo total de ejecucion: "
                + format_elapsed_seconds(
                    started_at=execution.started_at,
                    finished_at=execution.finished_at,
                )
            ),
            "",
            *step_lines,
            "",
            (
                "La ejecucion y todos sus pasos "
                "han quedado auditados."
            ),
            (
                "Puedes consultar el detalle con:"
            ),
            f"/ver_ejecucion {task_id}",
        ]

        return (
            "\n".join(lines),
            {
                "route": route,
                "task_id": execution.task_id,
                "execution_id": execution.id,
                "execution_status": (
                    execution.status.value
                ),
                "manifest_id": manifest.id,
                "manifest_version": (
                    manifest.version
                ),
                "manifest_hash": (
                    manifest.manifest_hash
                ),
                "attempt_id": attempt.id,
                "attempt_number": (
                    attempt.attempt_number
                ),
                "attempt_status": (
                    attempt.status.value
                ),
                "execution_elapsed_seconds": (
                    execution_elapsed_seconds
                ),
                "step_elapsed_seconds": (
                    step_elapsed_seconds
                ),
            },
        )

    def _process_generate_manifest_command(
        self,
        arguments: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = (
            "execution_action_generator"
        )

        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuyo "
                    "manifiesto quieres generar."
                    "\n\nEjemplo:\n"
                    "/generar_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/generar_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/generar_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if (
            self._execution_query_service
            is None
            or self._task_plan_repository
            is None
            or self._execution_action_generator
            is None
        ):
            return (
                (
                    "El servicio de generacion de "
                    "manifiestos no esta disponible."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            query_result = (
                self._execution_query_service
                .get_by_task_id(task_id)
            )

            execution = query_result.execution

            plan = (
                self._task_plan_repository
                .get_by_id(execution.plan_id)
            )

            if plan is None:
                raise (
                    ExecutionActionGenerationError(
                        "No existe el plan asociado "
                        "a la ejecucion"
                    )
                )

            if plan.task_id != execution.task_id:
                raise (
                    ExecutionActionGenerationError(
                        "El plan no pertenece a la "
                        "tarea de la ejecucion"
                    )
                )

            generation_result = (
                self
                ._execution_action_generator
                .generate(
                    execution_id=execution.id,
                    plan=plan,
                )
            )

        except (
            ExecutionQueryError,
            ExecutionActionGenerationError,
            ExecutionManifestConfirmationError,
        ) as error:
            return (
                str(error),
                {
                    "route": route,
                    "manifest_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        manifest = generation_result.manifest

        lines = [
            "MANIFIESTO GENERADO",
            "",
            f"Tarea: #{execution.task_id}",
            f"Ejecucion: #{execution.id}",
            f"Plan aprobado: #{plan.id}",
            f"Manifiesto: #{manifest.id}",
            f"Version: {manifest.version}",
            (
                "Hash: "
                f"{manifest.manifest_hash}"
            ),
            (
                "Acciones: "
                f"{manifest.action_count}"
            ),
            (
                "Acciones destructivas: "
                f"{manifest.destructive_action_count}"
            ),
            (
                "Modelo: "
                f"{generation_result.model}"
            ),
            (
                "Tiempo de generacion: "
                f"{generation_result.elapsed_seconds:.2f} "
                "segundos"
            ),
            "",
            (
                "Revisa todas las acciones con:"
            ),
            f"/ver_manifiesto {task_id}",
            "",
            (
                "El manifiesto queda pendiente "
                "de confirmacion."
            ),
            (
                "No se ha ejecutado ninguna accion."
            ),
        ]

        return (
            "\n".join(lines),
            {
                "route": route,
                "task_id": execution.task_id,
                "execution_id": execution.id,
                "plan_id": plan.id,
                "manifest_id": manifest.id,
                "manifest_version": (
                    manifest.version
                ),
                "manifest_hash": (
                    manifest.manifest_hash
                ),
                "action_count": (
                    manifest.action_count
                ),
                "destructive_action_count": (
                    manifest
                    .destructive_action_count
                ),
                "generation_model": (
                    generation_result.model
                ),
                "generation_elapsed_seconds": (
                    generation_result
                    .elapsed_seconds
                ),
            },
        )

    def _process_view_manifest_command(
        self,
        arguments: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = (
            "execution_manifest_service"
        )

        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuyo "
                    "manifiesto quieres consultar."
                    "\n\nEjemplo:\n"
                    "/ver_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/ver_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/ver_manifiesto 4"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if (
            self._execution_manifest_service
            is None
        ):
            return (
                (
                    "El servicio de manifiestos "
                    "no esta disponible."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            review = (
                self
                ._execution_manifest_service
                .get_by_task_id(task_id)
            )

        except (
            ExecutionManifestConfirmationError
        ) as error:
            return (
                str(error),
                {
                    "route": route,
                    "manifest_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        manifest = review.manifest

        lines = [
            f"MANIFIESTO #{manifest.id}",
            "",
            (
                "Ejecucion: "
                f"#{review.execution.id}"
            ),
            (
                "Tarea: "
                f"#{review.execution.task_id}"
            ),
            f"Version: {manifest.version}",
            (
                "Estado: "
                f"{manifest.status.value}"
            ),
            (
                "Hash: "
                f"{manifest.manifest_hash}"
            ),
            (
                "Acciones: "
                f"{manifest.action_count}"
            ),
            (
                "Acciones destructivas: "
                f"{manifest.destructive_action_count}"
            ),
            "",
            "ACCIONES",
        ]

        for action in review.actions:
            destructive_label = (
                " DESTRUCTIVA"
                if action.destructive
                else ""
            )

            lines.append(
                "Paso "
                f"{action.step_number}: "
                f"{action.name}\n"
                "  Tipo: "
                f"{action.action_type}\n"
                "  Ruta: "
                f"{action.relative_path}"
                f"{destructive_label}"
            )

        if (
            review
            .requires_extra_confirmation
        ):
            lines.extend(
                (
                    "",
                    (
                        "REQUIERE CONFIRMACION "
                        "DESTRUCTIVA"
                    ),
                )
            )

        lines.extend(
            (
                "",
                (
                    "La consulta no ejecuta "
                    "ninguna accion."
                ),
            )
        )

        return (
            "\n".join(lines),
            {
                "route": route,
                "execution_id": (
                    review.execution.id
                ),
                "task_id": (
                    review.execution.task_id
                ),
                "manifest_id": manifest.id,
                "manifest_version": (
                    manifest.version
                ),
                "manifest_status": (
                    manifest.status.value
                ),
                "manifest_hash": (
                    manifest.manifest_hash
                ),
                "action_count": (
                    manifest.action_count
                ),
                "destructive_action_count": (
                    manifest
                    .destructive_action_count
                ),
                "requires_extra_confirmation": (
                    review
                    .requires_extra_confirmation
                ),
            },
        )

    def _process_confirm_manifest_command(
        self,
        arguments: str,
        message_id: str,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = (
            "execution_manifest_confirmation"
        )

        parts = arguments.split()

        if len(parts) < 3:
            return (
                (
                    "Debes escribir CONFIRMAR "
                    "despues del identificador "
                    "y del hash.\n\n"
                    "Ejemplo:\n"
                    "/confirmar_manifiesto 4 "
                    "<hash> CONFIRMAR"
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "confirmation_required"
                    ),
                },
            )

        if len(parts) > 4:
            return (
                (
                    "El comando contiene "
                    "demasiados argumentos."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_task_id"
                    ),
                },
            )

        manifest_hash = (
            parts[1].strip().lower()
        )

        if (
            len(manifest_hash) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character
                in manifest_hash
            )
        ):
            return (
                (
                    "El hash del manifiesto debe "
                    "tener 64 caracteres "
                    "hexadecimales."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "invalid_manifest_hash"
                    ),
                    "task_id": task_id,
                },
            )

        if parts[2].upper() != "CONFIRMAR":
            return (
                (
                    "Debes escribir CONFIRMAR "
                    "exactamente."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "confirmation_required"
                    ),
                    "task_id": task_id,
                },
            )

        destructive_acknowledged = False

        if len(parts) == 4:
            if (
                parts[3].upper()
                != "DESTRUCTIVO"
            ):
                return (
                    (
                        "La confirmacion adicional "
                        "debe ser DESTRUCTIVO."
                    ),
                    {
                        "route": route,
                        "manifest_error": (
                            "invalid_destructive_ack"
                        ),
                        "task_id": task_id,
                    },
                )

            destructive_acknowledged = True

        if (
            self._execution_manifest_service
            is None
        ):
            return (
                (
                    "El servicio de manifiestos "
                    "no esta disponible."
                ),
                {
                    "route": route,
                    "manifest_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            manifest = (
                self
                ._execution_manifest_service
                .confirm(
                    task_id=task_id,
                    expected_manifest_hash=(
                        manifest_hash
                    ),
                    confirmed_by_user_id=(
                        user_id
                    ),
                    confirmation_message_id=(
                        message_id
                    ),
                    confirmation_channel=(
                        channel
                    ),
                    destructive_acknowledged=(
                        destructive_acknowledged
                    ),
                )
            )

        except (
            ExecutionManifestConfirmationError
        ) as error:
            return (
                str(error),
                {
                    "route": route,
                    "manifest_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        text = (
            "MANIFIESTO CONFIRMADO\n\n"
            f"Manifiesto: #{manifest.id}\n"
            "Ejecucion: "
            f"#{manifest.execution_id}\n"
            f"Version: {manifest.version}\n"
            "Estado: "
            f"{manifest.status.value}\n"
            "Hash: "
            f"{manifest.manifest_hash}\n"
            "Acciones: "
            f"{manifest.action_count}\n"
            "Acciones destructivas: "
            f"{manifest.destructive_action_count}"
            "\n\n"
            "La confirmacion no inicia "
            "la ejecucion."
        )

        return (
            text,
            {
                "route": route,
                "task_id": task_id,
                "execution_id": (
                    manifest.execution_id
                ),
                "manifest_id": manifest.id,
                "manifest_version": (
                    manifest.version
                ),
                "manifest_status": (
                    manifest.status.value
                ),
                "manifest_hash": (
                    manifest.manifest_hash
                ),
                "destructive_action_count": (
                    manifest
                    .destructive_action_count
                ),
            },
        )

    def _process_view_execution_command(
        self,
        arguments: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuya "
                    "ejecucion quieres consultar."
                    "\n\nEjemplo:\n"
                    "/ver_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_query_service"
                    ),
                    "execution_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/ver_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_query_service"
                    ),
                    "execution_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/ver_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_query_service"
                    ),
                    "execution_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if self._execution_query_service is None:
            return (
                (
                    "El servicio de consulta de "
                    "ejecuciones no esta "
                    "disponible."
                ),
                {
                    "route": (
                        "execution_query_service"
                    ),
                    "execution_error": (
                        "service_unavailable"
                    ),
                },
            )

        try:
            result = (
                self._execution_query_service
                .get_by_task_id(task_id)
            )

        except ExecutionQueryError as error:
            return (
                str(error),
                {
                    "route": (
                        "execution_query_service"
                    ),
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        execution = result.execution

        started_at = (
            execution.started_at
            or "no iniciado"
        )
        finished_at = (
            execution.finished_at
            or "no finalizado"
        )
        last_error = (
            execution.last_error
            or "ninguno"
        )

        lines = [
            f"EJECUCION #{execution.id}",
            "",
            f"Tarea: #{execution.task_id}",
            f"Plan: #{execution.plan_id}",
            (
                "Autorizacion: "
                f"#{execution.approval_id}"
            ),
            (
                "Estado: "
                f"{execution.status.value}"
            ),
            (
                "Workspace: "
                f"{execution.workspace_path}"
            ),
            (
                "Intentos: "
                f"{len(result.attempts)}"
            ),
            f"Pasos: {len(result.steps)}",
            f"Inicio: {started_at}",
            f"Fin: {finished_at}",
            f"Ultimo error: {last_error}",
        ]

        if result.attempts:
            lines.extend(
                (
                    "",
                    "DETALLE DE INTENTOS",
                )
            )

            for attempt in result.attempts:
                lines.append(
                    "Intento "
                    f"{attempt.attempt_number}: "
                    f"{attempt.status.value}"
                )

        if result.steps:
            lines.extend(
                (
                    "",
                    "DETALLE DE PASOS",
                )
            )

            for step in result.steps:
                lines.append(
                    "Paso "
                    f"{step.step_number}: "
                    f"{step.name} "
                    f"[{step.status.value}]"
                )

        if not result.attempts:
            lines.extend(
                (
                    "",
                    "No se ha iniciado codigo.",
                )
            )

        return (
            "\n".join(lines),
            {
                "route": (
                    "execution_query_service"
                ),
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "plan_id": execution.plan_id,
                "approval_id": (
                    execution.approval_id
                ),
                "execution_status": (
                    execution.status.value
                ),
                "attempt_count": len(
                    result.attempts
                ),
                "step_count": len(
                    result.steps
                ),
            },
        )

    def _process_prepare_promotion_command(
        self,
        arguments: str,
        message_id: str,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = (
            "promotion_preparation_service"
        )

        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuya "
                    "promocion quieres preparar."
                    "\n\nEjemplo:\n"
                    "/preparar_promocion 4"
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/preparar_promocion 4"
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/preparar_promocion 4"
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if (
            self._promotion_target_resolver
            is None
            or self
            ._promotion_preparation_service
            is None
        ):
            return (
                (
                    "El servicio de preparacion "
                    "de promociones no esta "
                    "disponible."
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            target = (
                self._promotion_target_resolver
                .resolve_task(task_id)
            )

            result = (
                self
                ._promotion_preparation_service
                .prepare(
                    execution_id=(
                        target.execution_id
                    ),
                    target_repository_root=(
                        target.repository_root
                    ),
                    requested_by_user_id=(
                        user_id
                    ),
                    request_message_id=(
                        message_id
                    ),
                    channel=channel,
                    target_subdirectory=(
                        target
                        .target_subdirectory
                    ),
                    test_target=(
                        target.test_target
                    ),
                )
            )

        except (
            PromotionTargetResolutionError,
            PromotionPreparationError,
        ) as error:
            return (
                str(error),
                {
                    "route": route,
                    "promotion_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        promotion = result.promotion
        preview = result.preview

        lines = [
            "PROMOCION PREPARADA",
            "",
            f"Tarea: #{task_id}",
            (
                "Ejecucion: "
                f"#{target.execution_id}"
            ),
            (
                "Promocion: "
                f"#{promotion.id}"
            ),
            (
                "Proyecto objetivo: "
                f"{target.target_project_name}"
            ),
            (
                "Subdirectorio: "
                f"{target.target_subdirectory}"
            ),
            (
                "Archivos modificados: "
                f"{preview.changed_count}"
            ),
            (
                "Nuevos: "
                f"{preview.added_count}"
            ),
            (
                "Actualizados: "
                f"{preview.modified_count}"
            ),
            (
                "Hash de vista previa: "
                f"{preview.preview_hash}"
            ),
            "",
            "Cambios:",
        ]

        for change in preview.changes:
            marker = (
                "+"
                if change.change_type.value
                == "added"
                else "~"
            )

            lines.append(
                f"{marker} "
                f"{change.relative_path}"
            )

        lines.extend(
            [
                "",
                (
                    "El repositorio no ha sido "
                    "modificado."
                ),
                (
                    "Para confirmar exactamente "
                    "esta vista previa:"
                ),
                (
                    "/confirmar_promocion "
                    f"{promotion.id}"
                ),
            ]
        )

        return (
            "\n".join(lines),
            {
                "route": route,
                "task_id": task_id,
                "execution_id": (
                    target.execution_id
                ),
                "promotion_id": promotion.id,
                "promotion_status": (
                    promotion.status.value
                ),
                "target_project_name": (
                    target.target_project_name
                ),
                "target_subdirectory": (
                    target.target_subdirectory
                ),
                "preview_hash": (
                    preview.preview_hash
                ),
                "changed_file_count": (
                    preview.changed_count
                ),
                "added_file_count": (
                    preview.added_count
                ),
                "modified_file_count": (
                    preview.modified_count
                ),
            },
        )

    def _process_view_promotion_command(
        self,
        arguments: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = "promotion_query_service"

        normalized_arguments = (
            arguments.strip()
        )

        if not normalized_arguments:
            return (
                (
                    "Debes indicar la promocion "
                    "que quieres consultar.\n\n"
                    "Ejemplo:\n"
                    "/ver_promocion 1"
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "missing_promotion_id"
                    ),
                },
            )

        parts = normalized_arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la "
                    "promocion.\n\n"
                    "Ejemplo:\n"
                    "/ver_promocion 1"
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            promotion_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la "
                    "promocion debe ser un "
                    "numero entero positivo."
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "invalid_promotion_id"
                    ),
                },
            )

        if promotion_id <= 0:
            return (
                (
                    "El identificador de la "
                    "promocion debe ser un "
                    "numero entero positivo."
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "invalid_promotion_id"
                    ),
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        if self._promotion_query_service is None:
            return (
                (
                    "El servicio de consulta de "
                    "promociones no esta "
                    "disponible."
                ),
                {
                    "route": route,
                    "promotion_error": (
                        "service_unavailable"
                    ),
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        try:
            promotion = (
                self
                ._promotion_query_service
                .get_by_id(promotion_id)
            )

        except PromotionQueryError as error:
            return (
                str(error),
                {
                    "route": route,
                    "promotion_error": (
                        type(error).__name__
                    ),
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        lines = [
            f"PROMOCION #{promotion.id}",
            "",
            (
                "Ejecucion: "
                f"#{promotion.execution_id}"
            ),
            (
                "Estado: "
                f"{promotion.status.value}"
            ),
            (
                "Proyecto destino: "
                f"{promotion.target_subdirectory}"
            ),
            (
                "Objetivo de pruebas: "
                f"{promotion.test_target}"
            ),
            (
                "Archivos cambiados: "
                f"{promotion.changed_file_count}"
            ),
            (
                "Archivos anadidos: "
                f"{promotion.added_file_count}"
            ),
            (
                "Archivos modificados: "
                f"{promotion.modified_file_count}"
            ),
            (
                "Hash de vista previa: "
                f"{promotion.preview_hash}"
            ),
            (
                "Solicitada por: "
                f"{promotion.requested_by_user_id}"
            ),
            (
                "Fecha de creacion: "
                f"{promotion.created_at}"
            ),
        ]

        if (
            promotion.confirmed_by_user_id
            is not None
        ):
            lines.append(
                "Confirmada por: "
                f"{promotion.confirmed_by_user_id}"
            )

        if promotion.confirmed_at is not None:
            lines.append(
                "Fecha de confirmacion: "
                f"{promotion.confirmed_at}"
            )

        if (
            promotion.promotion_branch
            is not None
        ):
            lines.append(
                "Rama temporal: "
                f"{promotion.promotion_branch}"
            )

        if promotion.base_commit is not None:
            lines.append(
                "Commit base: "
                f"{promotion.base_commit}"
            )

        if promotion.commit_hash is not None:
            lines.append(
                "Commit de promocion: "
                f"{promotion.commit_hash}"
            )

        if (
            promotion.sandbox_exit_code
            is not None
        ):
            lines.append(
                "Codigo de salida del sandbox: "
                f"{promotion.sandbox_exit_code}"
            )

        if (
            promotion.sandbox_timed_out
            is not None
        ):
            timed_out_text = (
                "si"
                if promotion.sandbox_timed_out
                else "no"
            )

            lines.append(
                "Timeout del sandbox: "
                f"{timed_out_text}"
            )

        if (
            promotion
            .sandbox_duration_seconds
            is not None
        ):
            lines.append(
                "Tiempo del sandbox: "
                f"{promotion.sandbox_duration_seconds:.3f} s"
            )

        if promotion.finished_at is not None:
            lines.append(
                "Fecha de finalizacion: "
                f"{promotion.finished_at}"
            )

        if promotion.error_message is not None:
            lines.extend(
                [
                    "",
                    "ERROR REGISTRADO",
                    promotion.error_message,
                ]
            )

        stdout_text = (
            promotion.sandbox_stdout_text
            or ""
        ).strip()

        stderr_text = (
            promotion.sandbox_stderr_text
            or ""
        ).strip()

        maximum_output_characters = 1500

        if stdout_text:
            if (
                len(stdout_text)
                > maximum_output_characters
            ):
                stdout_text = (
                    stdout_text[
                        :maximum_output_characters
                    ]
                    + "\n...[salida truncada]"
                )

            lines.extend(
                [
                    "",
                    "SALIDA DEL SANDBOX",
                    stdout_text,
                ]
            )

        if stderr_text:
            if (
                len(stderr_text)
                > maximum_output_characters
            ):
                stderr_text = (
                    stderr_text[
                        :maximum_output_characters
                    ]
                    + "\n...[salida truncada]"
                )

            lines.extend(
                [
                    "",
                    "ERRORES DEL SANDBOX",
                    stderr_text,
                ]
            )

        return (
            "\n".join(lines),
            {
                "route": route,
                "promotion_id": (
                    promotion.id
                ),
                "execution_id": (
                    promotion.execution_id
                ),
                "promotion_status": (
                    promotion.status.value
                ),
                "target_subdirectory": (
                    promotion
                    .target_subdirectory
                ),
                "preview_hash": (
                    promotion.preview_hash
                ),
                "promotion_branch": (
                    promotion.promotion_branch
                ),
                "base_commit": (
                    promotion.base_commit
                ),
                "commit_hash": (
                    promotion.commit_hash
                ),
                "sandbox_exit_code": (
                    promotion.sandbox_exit_code
                ),
                "sandbox_timed_out": (
                    promotion.sandbox_timed_out
                ),
                "sandbox_duration_seconds": (
                    promotion
                    .sandbox_duration_seconds
                ),
                "promotion_error_message": (
                    promotion.error_message
                ),
            },
        )

    def _process_confirm_promotion_command(
        self,
        arguments: str,
        message_id: str,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = "promotion_finalization_service"

        normalized_arguments = (
            arguments.strip()
        )

        if not normalized_arguments:
            return (
                (
                    "Debes indicar la promocion "
                    "que quieres confirmar.\n\n"
                    "Ejemplo:\n"
                    "/confirmar_promocion 1"
                ),
                {
                    "route": route,
                },
            )

        argument_parts = (
            normalized_arguments.split()
        )

        if len(argument_parts) != 1:
            return (
                (
                    "Debes indicar un unico "
                    "identificador de promocion.\n\n"
                    "Ejemplo:\n"
                    "/confirmar_promocion 1"
                ),
                {
                    "route": route,
                },
            )

        try:
            promotion_id = int(
                argument_parts[0]
            )

        except ValueError:
            return (
                (
                    "El identificador de la "
                    "promocion debe ser un "
                    "numero entero positivo."
                ),
                {
                    "route": route,
                },
            )

        if promotion_id <= 0:
            return (
                (
                    "El identificador de la "
                    "promocion debe ser un "
                    "numero entero positivo."
                ),
                {
                    "route": route,
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        if self._approval_service is None:
            return (
                (
                    "El servicio de autorizacion "
                    "no esta disponible."
                ),
                {
                    "route": route,
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        if (
            self
            ._promotion_finalization_service
            is None
        ):
            return (
                (
                    "El servicio de promocion "
                    "no esta disponible."
                ),
                {
                    "route": route,
                    "promotion_id": (
                        promotion_id
                    ),
                },
            )

        try:
            self._approval_service.ensure_approver(
                user_id
            )

            promotion = (
                self
                ._promotion_finalization_service
                .finalize(
                    promotion_id=promotion_id,
                    confirmed_by_user_id=(
                        user_id
                    ),
                    confirmation_message_id=(
                        message_id
                    ),
                    confirmation_channel=(
                        channel
                    ),
                )
            )

        except ApprovalError as error:
            return (
                str(error),
                {
                    "route": route,
                    "promotion_id": (
                        promotion_id
                    ),
                    "promotion_error": (
                        type(error).__name__
                    ),
                },
            )

        except (
            AuditedPromotionFinalizationError
        ) as error:
            metadata: dict[
                str,
                object,
            ] = {
                "route": route,
                "promotion_id": (
                    promotion_id
                ),
                "promotion_error": (
                    type(error).__name__
                ),
                "promotion_error_message": (
                    str(error)
                ),
            }

            sandbox_result = (
                error.sandbox_result
            )

            if sandbox_result is not None:
                metadata.update(
                    {
                        "sandbox_exit_code": (
                            sandbox_result
                            .exit_code
                        ),
                        "sandbox_timed_out": (
                            sandbox_result
                            .timed_out
                        ),
                        (
                            "sandbox_duration_seconds"
                        ): (
                            sandbox_result
                            .duration_seconds
                        ),
                    }
                )

            lines = [
                "NO SE PUDO CONFIRMAR "
                "LA PROMOCION",
                "",
                f"Promocion: #{promotion_id}",
                f"Error: {error}",
            ]

            if sandbox_result is not None:
                lines.extend(
                    [
                        "",
                        (
                            "Codigo de salida del "
                            "sandbox: "
                            f"{sandbox_result.exit_code}"
                        ),
                        (
                            "Tiempo del sandbox: "
                            f"{sandbox_result.duration_seconds:.3f} s"
                        ),
                    ]
                )

                stdout_text = (
                    sandbox_result
                    .stdout_text
                    .strip()
                )

                stderr_text = (
                    sandbox_result
                    .stderr_text
                    .strip()
                )

                if stdout_text:
                    lines.extend(
                        [
                            "",
                            "Salida de las pruebas:",
                            stdout_text,
                        ]
                    )

                if stderr_text:
                    lines.extend(
                        [
                            "",
                            "Errores de las pruebas:",
                            stderr_text,
                        ]
                    )

            return (
                "\n".join(lines),
                metadata,
            )

        lines = [
            "PROMOCION COMPLETADA",
            "",
            f"Promocion: #{promotion.id}",
            (
                "Ejecucion: "
                f"#{promotion.execution_id}"
            ),
            (
                "Estado: "
                f"{promotion.status.value}"
            ),
            (
                "Proyecto destino: "
                f"{promotion.target_subdirectory}"
            ),
            (
                "Archivos cambiados: "
                f"{promotion.changed_file_count}"
            ),
            (
                "Archivos anadidos: "
                f"{promotion.added_file_count}"
            ),
            (
                "Archivos modificados: "
                f"{promotion.modified_file_count}"
            ),
        ]

        if promotion.promotion_branch is not None:
            lines.append(
                "Rama temporal: "
                f"{promotion.promotion_branch}"
            )

        if promotion.base_commit is not None:
            lines.append(
                "Commit base: "
                f"{promotion.base_commit}"
            )

        if promotion.commit_hash is not None:
            lines.append(
                "Commit de promocion: "
                f"{promotion.commit_hash}"
            )

        if (
            promotion
            .sandbox_duration_seconds
            is not None
        ):
            lines.append(
                "Tiempo del sandbox: "
                f"{promotion.sandbox_duration_seconds:.3f} s"
            )

        lines.extend(
            [
                "",
                (
                    "La promocion ha quedado "
                    "validada, confirmada en Git "
                    "y registrada en la auditoria."
                ),
                (
                    "El commit permanece en la "
                    "rama temporal; no se ha "
                    "fusionado ni enviado al "
                    "repositorio remoto."
                ),
            ]
        )

        return (
            "\n".join(lines),
            {
                "route": route,
                "promotion_id": (
                    promotion.id
                ),
                "execution_id": (
                    promotion.execution_id
                ),
                "promotion_status": (
                    promotion.status.value
                ),
                "target_subdirectory": (
                    promotion
                    .target_subdirectory
                ),
                "promotion_branch": (
                    promotion.promotion_branch
                ),
                "base_commit": (
                    promotion.base_commit
                ),
                "commit_hash": (
                    promotion.commit_hash
                ),
                "sandbox_exit_code": (
                    promotion.sandbox_exit_code
                ),
                "sandbox_timed_out": (
                    promotion.sandbox_timed_out
                ),
                "sandbox_duration_seconds": (
                    promotion
                    .sandbox_duration_seconds
                ),
                "changed_file_count": (
                    promotion
                    .changed_file_count
                ),
            },
        )

    def _process_prepare_execution_command(
        self,
        arguments: str,
        message_id: str,
        user_id: str,
        channel: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuya "
                    "ejecucion quieres preparar."
                    "\n\nEjemplo:\n"
                    "/preparar_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_preparation_service"
                    ),
                    "execution_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/preparar_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_preparation_service"
                    ),
                    "execution_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/preparar_ejecucion 4"
                ),
                {
                    "route": (
                        "execution_preparation_service"
                    ),
                    "execution_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if (
            self._execution_preparation_service
            is None
        ):
            return (
                (
                    "El servicio de preparacion "
                    "de ejecuciones no esta "
                    "disponible."
                ),
                {
                    "route": (
                        "execution_preparation_service"
                    ),
                    "execution_error": (
                        "service_unavailable"
                    ),
                },
            )

        try:
            result = (
                self
                ._execution_preparation_service
                .prepare(
                    task_id=task_id,
                    requested_by_user_id=(
                        user_id
                    ),
                    request_message_id=(
                        message_id
                    ),
                    channel=channel,
                )
            )

        except ExecutionPreparationError as error:
            return (
                str(error),
                {
                    "route": (
                        "execution_preparation_service"
                    ),
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        execution = result.execution

        if result.already_prepared:
            heading = (
                "EJECUCION YA PREPARADA"
            )
        else:
            heading = "EJECUCION PREPARADA"

        text = (
            f"{heading}\n\n"
            f"Ejecucion: #{execution.id}\n"
            f"Tarea: #{execution.task_id}\n"
            f"Plan: #{execution.plan_id}\n"
            "Autorizacion: "
            f"#{execution.approval_id}\n"
            "Estado: "
            f"{execution.status.value}\n"
            "Workspace: "
            f"{execution.workspace_path}\n\n"
            "No se ha ejecutado codigo."
        )

        return (
            text,
            {
                "route": (
                    "execution_preparation_service"
                ),
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "plan_id": execution.plan_id,
                "approval_id": (
                    execution.approval_id
                ),
                "execution_status": (
                    execution.status.value
                ),
                "workspace_path": (
                    execution.workspace_path
                ),
                "already_prepared": (
                    result.already_prepared
                ),
            },
        )

    def _process_cancel_execution_command(
        self,
        arguments: str,
        user_id: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        route = (
            "execution_cancellation_service"
        )

        if not arguments:
            return (
                (
                    "Debes indicar la tarea cuya "
                    "ejecucion quieres cancelar."
                    "\n\nEjemplo:\n"
                    "/cancelar_ejecucion 4"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/cancelar_ejecucion 4"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/cancelar_ejecucion 4"
                ),
                {
                    "route": route,
                    "execution_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if self._execution_query_service is None:
            return (
                (
                    "El servicio de consulta de "
                    "ejecuciones no esta "
                    "disponible."
                ),
                {
                    "route": route,
                    "execution_error": (
                        "service_unavailable"
                    ),
                    "task_id": task_id,
                },
            )

        try:
            current = (
                self._execution_query_service
                .get_by_task_id(task_id)
            )

        except ExecutionQueryError as error:
            return (
                str(error),
                {
                    "route": route,
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        if current.execution.task_id != task_id:
            raise RuntimeError(
                "La ejecucion no corresponde "
                "a la tarea indicada"
            )

        text, cancellation_metadata = (
            self._process_cancel_command(
                arguments=arguments,
                user_id=user_id,
            )
        )

        if (
            "cancellation_error"
            in cancellation_metadata
        ):
            metadata = dict(
                cancellation_metadata
            )
            metadata["route"] = route
            metadata["execution_error"] = (
                metadata.pop(
                    "cancellation_error"
                )
            )

            return text, metadata

        try:
            updated = (
                self._execution_query_service
                .get_by_task_id(task_id)
            )

        except ExecutionQueryError as error:
            return (
                str(error),
                {
                    "route": route,
                    "execution_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        execution = updated.execution

        metadata = dict(
            cancellation_metadata
        )
        metadata.update(
            {
                "route": route,
                "execution_id": (
                    execution.id
                ),
                "execution_status": (
                    execution.status.value
                ),
            }
        )

        return (
            (
                f"{text}\n\n"
                "Ejecucion asociada: "
                f"#{execution.id} "
                f"({execution.status.value})."
            ),
            metadata,
        )

    def _process_cancel_command(
        self,
        arguments: str,
        user_id: str,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea que "
                    "quieres cancelar.\n\n"
                    "Ejemplo:\n"
                    "/cancelar 3"
                ),
                {
                    "route": "cancellation_service",
                    "cancellation_error": (
                        "missing_task_id"
                    ),
                },
            )

        parts = arguments.split()

        if len(parts) != 1:
            return (
                (
                    "El comando solamente admite "
                    "el identificador de la tarea."
                    "\n\nEjemplo:\n"
                    "/cancelar 3"
                ),
                {
                    "route": "cancellation_service",
                    "cancellation_error": (
                        "invalid_arguments"
                    ),
                },
            )

        try:
            task_id = int(parts[0])

        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un numero entero."
                    "\n\nEjemplo:\n"
                    "/cancelar 3"
                ),
                {
                    "route": "cancellation_service",
                    "cancellation_error": (
                        "invalid_task_id"
                    ),
                },
            )

        if self._approval_service is None:
            return (
                (
                    "El servicio de cancelacion "
                    "no esta disponible."
                ),
                {
                    "route": "cancellation_service",
                    "cancellation_error": (
                        "service_unavailable"
                    ),
                },
            )

        try:
            result = (
                self._approval_service.cancel(
                    task_id=task_id,
                    authorized_user_id=user_id,
                )
            )

        except ApprovalError as error:
            return (
                str(error),
                {
                    "route": "cancellation_service",
                    "cancellation_error": (
                        type(error).__name__
                    ),
                    "task_id": task_id,
                },
            )

        text = (
            self._approval_formatter
            .format_cancellation(result)
        )

        return (
            text,
            {
                "route": "cancellation_service",
                "task_id": result.task.id,
                "task_status": (
                    result.task.status.value
                ),
                "plan_id": result.plan.id,
                "plan_version": (
                    result.plan.version
                ),
                "plan_status": (
                    result.plan.status.value
                ),
                "approval_id": (
                    result.approval.id
                ),
                "cancelled_user_id": (
                    result.cancelled_user_id
                ),
                "already_cancelled": (
                    result.already_cancelled
                ),
            },
        )

    def _process_respond_command(
        self,
        arguments: str,
        message_id: str,
        session_id: int,
    ) -> tuple[
        str,
        dict[str, object],
    ]:
        if not arguments:
            return (
                (
                    "Debes indicar la tarea y "
                    "la respuesta.\n\n"
                    "Ejemplo:\n"
                    "/responder 2 Será una "
                    "aplicación web para móvil."
                ),
                {},
            )

        parts = arguments.split(
            maxsplit=1
        )

        if len(parts) < 2:
            return (
                (
                    "Debes indicar también "
                    "las aclaraciones.\n\n"
                    "Ejemplo:\n"
                    "/responder 2 Será una "
                    "aplicación web para móvil."
                ),
                {},
            )

        task_id_text = parts[0].strip()
        answer = parts[1].strip()

        try:
            task_id = int(task_id_text)
        except ValueError:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser un número entero."
                ),
                {},
            )

        if task_id <= 0:
            return (
                (
                    "El identificador de la tarea "
                    "debe ser mayor que cero."
                ),
                {},
            )

        if not answer:
            return (
                (
                    "La respuesta no puede "
                    "estar vacía."
                ),
                {},
            )

        if (
            self._clarification_workflow_service
            is None
        ):
            return (
                (
                    "El servicio de planificación "
                    "no está configurado."
                ),
                {
                    "route": (
                        "clarification_workflow"
                    ),
                    "error": (
                        "PlanningServiceNotConfigured"
                    ),
                },
            )

        try:
            result = (
                self
                ._clarification_workflow_service
                .respond(
                    task_id=task_id,
                    session_id=session_id,
                    response_message_id=(
                        message_id
                    ),
                    answer=answer,
                )
            )

        except (
            ValueError,
            LanguageProviderError,
            PlanningGenerationError,
        ) as error:
            return (
                (
                    "No se ha podido procesar "
                    "la aclaración.\n\n"
                    f"{error}"
                ),
                {
                    "route": (
                        "clarification_workflow"
                    ),
                    "error": (
                        type(error).__name__
                    ),
                    "error_message": str(error),
                },
            )

        plan = result.generated_plan.plan

        response_text = (
            self._planning_formatter.format(
                plan=plan,
                task=result.task,
            )
        )

        return (
            response_text,
            {
                "route": (
                    "clarification_workflow"
                ),
                "task_id": result.task.id,
                "task_status": (
                    result.task.status.value
                ),
                "plan_id": plan.id,
                "plan_version": plan.version,
                "plan_status": (
                    plan.status.value
                ),
                "model": (
                    result.generated_plan.model
                ),
                "elapsed_seconds": (
                    result.generated_plan
                    .elapsed_seconds
                ),
            },
        )

    def _process_classify_command(
        self,
        arguments: str,
    ) -> str:
        if not arguments:
            return (
                "Debes indicar una petición.\n\n"
                "Ejemplo:\n"
                "/clasificar Añade un "
                "canal de correo"
            )

        decision = (
            self._request_classifier.classify(
                arguments
            )
        )

        lines = [
            "CLASIFICACIÓN DE LA PETICIÓN",
            "",
            f"Petición: {decision.summary}",
            f"Tipo: {decision.kind.value}",
            (
                "Confianza: "
                f"{decision.confidence:.0%}"
            ),
            (
                "Necesita aclaración: "
                + (
                    "Sí"
                    if decision.requires_clarification
                    else "No"
                )
            ),
        ]

        if decision.project_name is not None:
            lines.append(
                "Proyecto: "
                f"{decision.project_name}"
            )

        if decision.missing_information:
            lines.extend(
                [
                    "",
                    "Información necesaria:",
                ]
            )

            for information in (
                decision.missing_information
            ):
                lines.append(
                    f"- {information}"
                )

        return "\n".join(lines)

    @staticmethod
    def _format_context(
        summary: ContextSummary,
    ) -> str:
        lines = [
            "Contexto del Agente Orquestador",
            "",
            f"Proyecto: {summary.project_name}",
            (
                "Sesiones: "
                f"{summary.total_sessions} "
                f"({summary.active_sessions} activas)"
            ),
            (
                "Mensajes registrados: "
                f"{summary.total_messages}"
            ),
            (
                "Documentos: "
                f"{summary.total_documents}"
            ),
            (
                "Commits: "
                f"{summary.total_commits}"
            ),
        ]

        if summary.recent_documents:
            lines.extend(
                [
                    "",
                    "Documentos recientes:",
                ]
            )

            for document in (
                summary.recent_documents
            ):
                title = (
                    document.title
                    or document.relative_path
                )

                lines.append(
                    f"- {title}"
                )

        if summary.recent_commits:
            lines.extend(
                [
                    "",
                    "Commits recientes:",
                ]
            )

            for commit in summary.recent_commits:
                lines.append(
                    f"- {commit.commit_hash[:7]} "
                    f"{commit.subject}"
                )

        return "\n".join(lines)
