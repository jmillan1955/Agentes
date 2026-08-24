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

        if message.content_type == ContentType.COMMAND:
            response_text = self._process_command(
                text=message.text,
                message_id=message.message_id,
            )

        elif message.content_type == ContentType.TEXT:
            try:
                answer = (
                    self._response_generation_service
                    .generate(
                        project_id=self._project_id,
                        query=message.text or "",
                        current_message_id=(
                            message.message_id
                        ),
                    )
                )

                response_text = answer.text

                metadata.update(
                    {
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
                        "error": (
                            type(error).__name__
                        ),
                        "error_message": str(error),
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
            conversation_id=message.conversation_id,
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
            "/buscar <consulta>"
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