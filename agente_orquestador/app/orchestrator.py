from __future__ import annotations

from app.context import (
    ContextBuilder,
    ContextQueryService,
    ContextSummary,
    MessageRepository,
    SessionRepository,
    TaskRepository,
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
    ) -> None:
        self._project_id = project_id
        self._context_builder = context_builder

        self._session_repository = (
            session_repository
        )
        self._message_repository = (
            message_repository
        )
        self._task_repository = (
            task_repository
        )
        self._context_query_service = (
            context_query_service
        )
        self._response_generation_service = (
            response_generation_service
        )

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
                "/simple <pregunta>"
            ),
            {},
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