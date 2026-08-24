from __future__ import annotations

from app.context.context_search_service import (
    ContextSearchService,
)
from app.context.models import ContextBlock


class ContextBuilder:
    def __init__(
        self,
        search_service: ContextSearchService,
    ) -> None:
        self._search_service = search_service

    def build(
        self,
        project_id: int,
        query: str,
        current_message_id: str | None = None,
        document_limit: int = 3,
        message_limit: int = 5,
        maximum_characters: int = 6000,
    ) -> ContextBlock:
        if maximum_characters < 100:
            raise ValueError(
                "maximum_characters debe ser "
                "al menos 100"
            )

        document_result = (
            self._search_service
            .search_documents(
                project_id=project_id,
                query=query,
                limit=document_limit,
            )
        )

        message_result = (
            self._search_service
            .search_messages(
                project_id=project_id,
                query=query,
                limit=message_limit,
                exclude_message_id=(
                    current_message_id
                ),
            )
        )

        lines = [
            "CONTEXTO RECUPERADO",
            "",
            f"Consulta: {query.strip()}",
        ]

        if document_result.documents:
            lines.extend(
                [
                    "",
                    "DOCUMENTOS RELEVANTES",
                ]
            )

            for document in (
                document_result.documents
            ):
                title = (
                    document.title
                    or document.relative_path
                )

                lines.extend(
                    [
                        "",
                        (
                            f"[Documento: {title} | "
                            f"puntuación: "
                            f"{document.score}]"
                        ),
                        (
                            "Documento fuente: "
                            f"{document.relative_path}"
                        ),                        
                        document.excerpt,
                    ]
                )

        if message_result.messages:
            lines.extend(
                [
                    "",
                    "CONVERSACIONES RELEVANTES",
                ]
            )

            for message in (
                message_result.messages
            ):
                lines.extend(
                    [
                        "",
                        (
                            "[Mensaje "
                            f"{message.direction} | "
                            f"puntuación: "
                            f"{message.score}]"
                        ),
                        message.text,
                    ]
                )

        if (
            not document_result.documents
            and not message_result.messages
        ):
            lines.extend(
                [
                    "",
                    (
                        "No se encontró contexto "
                        "relacionado."
                    ),
                ]
            )

        complete_text = "\n".join(lines)
        truncated = (
            len(complete_text)
            > maximum_characters
        )

        if truncated:
            text = (
                complete_text[
                    :maximum_characters - 3
                ].rstrip()
                + "..."
            )
        else:
            text = complete_text

        return ContextBlock(
            query=query.strip(),
            text=text,
            document_paths=tuple(
                document.relative_path
                for document
                in document_result.documents
            ),
            message_ids=tuple(
                message.message_id
                for message
                in message_result.messages
            ),
            total_characters=len(text),
            truncated=truncated,
        )