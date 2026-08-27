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
    ExecutionRunner,
)
from app.execution.service import (
    ExecutionPreparationError,
    ExecutionPreparationService,
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
        execution_runner: (
            ExecutionRunner | None
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
        self._execution_runner = (
            execution_runner
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
        if command == "/ver_ejecucion":
            return (
                self
                ._process_view_execution_command(
                    arguments
                )
            )
        if command == "/ver_plan":
            return self._process_view_plan_command(
                arguments
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
                "Comando no reconocido.\n\n"
                "Comandos disponibles:\n"
                "/contexto\n"
                "/buscar <consulta>\n"
                "/clasificar <petición>\n"
                "/responder <tarea_id> "
                "<aclaraciones>\n"
                "/ver_plan <tarea_id>\n"
                "/ver_ejecucion "
                "<tarea_id>\n"
                "/aprobar <tarea_id>\n"
                "/preparar_ejecucion "
                "<tarea_id>\n"
                "/cancelar <tarea_id>\n"
                "/simple <pregunta>"
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