from __future__ import annotations

import re
import unicodedata

from app.context.document_repository import (
    DocumentRepository,
)
from app.context.models import (
    ContextDocumentMatch,
    ContextMessageMatch,
    ContextMessageSearchResult,
    ContextSearchResult,
    DocumentRecord,
    MessageRecord,
)
from app.context.message_repository import (
    MessageRepository,
)

WORD_PATTERN = re.compile(r"[a-z0-9]+")

STOP_WORDS = {
    "a",
    "al",
    "como",
    "con",
    "cual",
    "cuando",
    "de",
    "del",
    "desde",
    "donde",
    "el",
    "en",
    "es",
    "esta",
    "este",
    "la",
    "las",
    "lo",
    "los",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "un",
    "una",
    "y",
}


class ContextSearchService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._document_repository = (
            document_repository
        )
        self._message_repository = (
            message_repository
        )

    def search_documents(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
    ) -> ContextSearchResult:
        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero"
            )

        clean_query = query.strip()

        if not clean_query:
            return ContextSearchResult(
                query=query,
                terms=(),
                documents=(),
            )

        terms = self._extract_terms(
            clean_query
        )

        if not terms:
            return ContextSearchResult(
                query=clean_query,
                terms=(),
                documents=(),
            )

        documents = (
            self._document_repository
            .list_by_project(project_id)
        )

        matches = []

        for document in documents:
            match = self._evaluate_document(
                document=document,
                terms=terms,
            )

            if match is not None:
                matches.append(match)

        matches.sort(
            key=lambda item: (
                -item.score,
                item.relative_path,
            )
        )

        return ContextSearchResult(
            query=clean_query,
            terms=terms,
            documents=tuple(
                matches[:limit]
            ),
        )

    def search_messages(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
        source_limit: int = 100,
        exclude_message_id: str | None = None,
    ) -> ContextMessageSearchResult:
        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero"
            )

        if source_limit <= 0:
            raise ValueError(
                "source_limit debe ser "
                "mayor que cero"
            )

        clean_query = query.strip()

        if not clean_query:
            return ContextMessageSearchResult(
                query=query,
                terms=(),
                messages=(),
            )

        terms = self._extract_terms(
            clean_query
        )

        if not terms:
            return ContextMessageSearchResult(
                query=clean_query,
                terms=(),
                messages=(),
            )

        messages = (
            self._message_repository
            .list_by_project(
                project_id=project_id,
                limit=source_limit,
            )
        )

        matches = []

        for message in messages:
            if (
                exclude_message_id is not None
                and message.message_id
                == exclude_message_id
            ):
                continue

            match = self._evaluate_message(
                message=message,
                terms=terms,
            )

            if match is not None:
                matches.append(
                    (
                        match,
                        message.id,
                    )
                )

        matches.sort(
            key=lambda item: (
                -item[0].score,
                -item[1],
            )
        )

        return ContextMessageSearchResult(
            query=clean_query,
            terms=terms,
            messages=tuple(
                item[0]
                for item in matches[:limit]
            ),
        )


    def _evaluate_document(
        self,
        document: DocumentRecord,
        terms: tuple[str, ...],
    ) -> ContextDocumentMatch | None:
        normalized_title = self._normalize(
            document.title or ""
        )
        normalized_path = self._normalize(
            document.relative_path
        )
        normalized_content = self._normalize(
            document.content
        )

        score = 0
        matched_terms = []

        for term in terms:
            term_score = 0

            if term in normalized_title:
                term_score += 5

            if term in normalized_path:
                term_score += 3

            if term in normalized_content:
                term_score += 1

            if term_score > 0:
                score += term_score
                matched_terms.append(term)

        if score == 0:
            return None

        return ContextDocumentMatch(
            document_id=document.id,
            relative_path=(
                document.relative_path
            ),
            title=document.title,
            score=score,
            matched_terms=tuple(
                matched_terms
            ),
            excerpt=self._create_excerpt(
                document.content
            ),
        )

    def _evaluate_message(
        self,
        message: MessageRecord,
        terms: tuple[str, ...],
    ) -> ContextMessageMatch | None:
        text = message.text or ""
        normalized_text = self._normalize(
            text
        )

        matched_terms = tuple(
            term
            for term in terms
            if term in normalized_text
        )

        if not matched_terms:
            return None

        score = len(matched_terms) * 2

        if message.direction == "incoming":
            score += 1

        return ContextMessageMatch(
            message_id=message.message_id,
            session_id=message.session_id,
            direction=message.direction,
            text=self._create_excerpt(text),
            score=score,
            matched_terms=matched_terms,
            created_at=message.created_at,
        )


    @classmethod
    def _extract_terms(
        cls,
        text: str,
    ) -> tuple[str, ...]:
        normalized = cls._normalize(text)

        terms = []
        seen = set()

        for term in WORD_PATTERN.findall(
            normalized
        ):
            if term in STOP_WORDS:
                continue

            if len(term) < 3:
                continue

            if term in seen:
                continue

            seen.add(term)
            terms.append(term)

        return tuple(terms)

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:
        decomposed = unicodedata.normalize(
            "NFKD",
            text.lower(),
        )

        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(
                character
            )
        )

    @staticmethod
    def _create_excerpt(
        content: str,
        maximum_length: int = 240,
    ) -> str:
        compact_content = " ".join(
            content.split()
        )

        if len(compact_content) <= maximum_length:
            return compact_content

        return (
            compact_content[
                :maximum_length
            ].rstrip()
            + "..."
        )