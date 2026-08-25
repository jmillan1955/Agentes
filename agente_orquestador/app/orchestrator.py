from __future__ import annotations

from app.context import (
    ContextBuilder,
    ContextQueryService,
    ContextSummary,
    MessageRepository,
    SessionRepository,
)
from app.models import (
    ContentType,
    IncomingMessage,
    OutgoingMessage,
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


class Orchestrator:
    def __init__(
        self,
        project_id: int,
        session_repository: SessionRepository,
        message_repository: MessageRepository,
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
    ) -> None:
        self._project_id = project_id
        self._context_builder = context_builder
        self._session_repository = (
            session_repository
        )
        self._message_repository = (
            message_repository
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
        metadata = {
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
                        decision.requires_clarification
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
            response_text = self._process_command(
                text=message.text,
                message_id=message.message_id,
            )

        elif message.content_type == ContentType.TEXT:
            if (
                decision is not None
                and decision.kind
                == RequestKind.TASK
            ):
                task_result = (
                    self._task_handler.handle(
                        decision
                    )
                )

                response_text = task_result.text

                metadata.update(
                    {
                        "route": "task_handler",
                        "task_status": (
                            task_result.status
                        ),
                        "task_project": (
                            task_result.project_name
                        ),
                    }
                )

            else:
                try:
                    answer = (
                        self._response_generation_service
                        .generate(
                            project_id=(
                                self._project_id
                            ),
                            query=message.text or "",
                            current_message_id=(
                                message.message_id
                            ),
                        )
                    )

                    response_text = answer.text

                    metadata.update(
                        {
                            "route": (
                                "language_provider"
                            ),
                            "model": answer.model,
                            "elapsed_seconds": (
                                answer.elapsed_seconds
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
                    )

                except LanguageProviderError as error:
                    response_text = (
                        "No se ha podido generar "
                        "la respuesta.\n\n"
                        f"{error}"
                    )

                    metadata.update(
                        {
                            "route": (
                                "language_provider"
                            ),
                            "error": (
                                type(error).__name__
                            ),
                            "error_message": str(
                                error
                            ),
                        }
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

    def _process_command(
        self,
        text: str | None,
        message_id: str,
    ) -> str:
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

        if command == "/clasificar":
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

        if command == "/contexto":
            summary = (
                self._context_query_service
                .get_summary(self._project_id)
            )

            return self._format_context(
                summary
            )

        if command == "/buscar":
            if not arguments:
                return (
                    "Debes indicar qué quieres "
                    "buscar.\n\n"
                    "Ejemplo:\n"
                    "/buscar integración Telegram"
                )

            context = self._context_builder.build(
                project_id=self._project_id,
                query=arguments,
                current_message_id=message_id,
                maximum_characters=3900,
            )

            return context.text

        return (
            "Comando no reconocido.\n\n"
            "Comandos disponibles:\n"
            "/contexto\n"
            "/buscar <consulta>\n"
            "/clasificar <petición>"
        )

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