from __future__ import annotations

from app.context import (
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


class Orchestrator:
    def __init__(
        self,
        project_id: int,
        session_repository: SessionRepository,
        message_repository: MessageRepository,
        context_query_service: ContextQueryService,
    ) -> None:
        self._project_id = project_id
        self._session_repository = (
            session_repository
        )
        self._message_repository = (
            message_repository
        )
        self._context_query_service = (
            context_query_service
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
        if message.content_type == ContentType.COMMAND:
            response_text = self._process_command(
                message.text
            )

        elif message.content_type == ContentType.TEXT:
            response_text = (
                "He recibido correctamente tu mensaje:\n\n"
                f"{message.text}"
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
            metadata={
                "processor": (
                    "provisional_orchestrator"
                ),
                "session_id": session_id,
            },
        )

    def _process_command(
        self,
        text: str | None,
    ) -> str:
        command = (
            (text or "")
            .strip()
            .split(maxsplit=1)[0]
            .split("@", maxsplit=1)[0]
            .lower()
        )

        if command == "/contexto":
            summary = (
                self._context_query_service
                .get_summary(self._project_id)
            )

            return self._format_context(
                summary
            )

        return (
            "Comando no reconocido.\n\n"
            "Comandos disponibles:\n"
            "/contexto"
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