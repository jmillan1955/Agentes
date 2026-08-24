from __future__ import annotations

from dataclasses import dataclass

from app.context import ContextBuilder
from app.prompt_builder import PromptBuilder
from app.providers import LanguageProvider


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    text: str
    model: str
    elapsed_seconds: float
    document_paths: tuple[str, ...]
    message_ids: tuple[str, ...]
    context_characters: int
    context_truncated: bool


class ResponseGenerationService:
    def __init__(
        self,
        context_builder: ContextBuilder,
        prompt_builder: PromptBuilder,
        language_provider: LanguageProvider,
        maximum_context_characters: int = 2500,
    ) -> None:
        if maximum_context_characters < 100:
            raise ValueError(
                "maximum_context_characters "
                "debe ser al menos 100"
            )

        self._context_builder = (
            context_builder
        )
        self._prompt_builder = prompt_builder
        self._language_provider = (
            language_provider
        )
        self._maximum_context_characters = (
            maximum_context_characters
        )

    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
    ) -> GeneratedAnswer:
        context = self._context_builder.build(
            project_id=project_id,
            query=query,
            current_message_id=(
                current_message_id
            ),
            maximum_characters=(
                self._maximum_context_characters
            ),
            document_limit=2,
            message_limit=3,
        )

        prompt = self._prompt_builder.build(
            query=query,
            context=context,
        )

        response = (
            self._language_provider.generate(
                prompt=prompt.user_prompt,
                system_prompt=(
                    prompt.system_prompt
                ),
            )
        )

        return GeneratedAnswer(
            text=response.text,
            model=response.model,
            elapsed_seconds=(
                response.elapsed_seconds
            ),
            document_paths=(
                context.document_paths
            ),
            message_ids=context.message_ids,
            context_characters=(
                context.total_characters
            ),
            context_truncated=(
                context.truncated
            ),
        )