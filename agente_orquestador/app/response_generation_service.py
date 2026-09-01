from __future__ import annotations

from dataclasses import dataclass

from app.context import (
    ContextBlock,
    ContextBuilder,
)
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
    provider: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


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
        include_context: bool = True,
        response_style: str | None = None,
    ) -> GeneratedAnswer:
        if include_context:
            context = self._context_builder.build(
                project_id=project_id,
                query=query,
                current_message_id=(
                    current_message_id
                ),
                maximum_characters=(
                    self
                    ._maximum_context_characters
                ),
                document_limit=2,
                message_limit=3,
            )

        else:
            context = ContextBlock(
                query=query,
                text="",
                document_paths=(),
                message_ids=(),
                total_characters=0,
                truncated=False,
            )

        prompt_query = query

        if response_style == "simple":
            prompt_query = "\n".join(
                [
                    (
                        "Responde únicamente en "
                        "español."
                    ),
                    (
                        "Utiliza como máximo dos "
                        "frases y 60 palabras."
                    ),
                    (
                        "No añadas introducciones, "
                        "ejemplos ni conclusiones."
                    ),
                    "",
                    "PREGUNTA",
                    query,
                ]
            )

        prompt = self._prompt_builder.build(
            query=prompt_query,
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
            provider=response.provider,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost_usd=(
                response.estimated_cost_usd
            ),
        )
