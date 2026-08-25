from __future__ import annotations

import pytest

from app.context import ContextBlock
from app.prompt_builder import PromptBuilder
from app.providers import LanguageResponse
from app.response_generation_service import (
    ResponseGenerationService,
)


class FakeContextBuilder:
    def __init__(self) -> None:
        self.build_calls = 0
        self.received_project_id = None
        self.received_query = None
        self.received_message_id = None
        self.received_maximum = None

    def build(
        self,
        project_id: int,
        query: str,
        current_message_id: str | None = None,
        document_limit: int = 3,
        message_limit: int = 5,
        maximum_characters: int = 6000,
    ) -> ContextBlock:
        self.build_calls += 1
        self.received_project_id = project_id
        self.received_query = query
        self.received_message_id = (
            current_message_id
        )
        self.received_maximum = (
            maximum_characters
        )

        text = (
            "CONTEXTO RECUPERADO\n"
            "El proyecto utiliza SQLite."
        )

        return ContextBlock(
            query=query,
            text=text,
            document_paths=(
                "docs/contexto.md",
            ),
            message_ids=(
                "mensaje-anterior",
            ),
            total_characters=len(text),
            truncated=False,
        )


class FakeLanguageProvider:
    def __init__(self) -> None:
        self.received_prompt = None
        self.received_system_prompt = None

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LanguageResponse:
        self.received_prompt = prompt
        self.received_system_prompt = (
            system_prompt
        )

        return LanguageResponse(
            text=(
                "El contexto se almacena "
                "en SQLite."
            ),
            model="modelo-de-prueba",
            elapsed_seconds=1.25,
        )


def test_generates_answer_with_context() -> None:
    context_builder = FakeContextBuilder()
    provider = FakeLanguageProvider()

    service = ResponseGenerationService(
        context_builder=context_builder,
        prompt_builder=PromptBuilder(),
        language_provider=provider,
    )

    answer = service.generate(
        project_id=7,
        query=(
            "Â¿DÃ³nde se almacena "
            "el contexto?"
        ),
        current_message_id="mensaje-actual",
    )

    assert answer.text == (
        "El contexto se almacena en SQLite."
    )
    assert answer.model == (
        "modelo-de-prueba"
    )
    assert answer.elapsed_seconds == 1.25
    assert answer.document_paths == (
        "docs/contexto.md",
    )
    assert answer.message_ids == (
        "mensaje-anterior",
    )

    assert context_builder.build_calls == 1
    assert (
        context_builder.received_project_id
        == 7
    )
    assert (
        context_builder.received_message_id
        == "mensaje-actual"
    )

    assert provider.received_prompt is not None
    assert "El proyecto utiliza SQLite" in (
        provider.received_prompt
    )
    assert (
        "Â¿DÃ³nde se almacena el contexto?"
        in provider.received_prompt
    )
    assert (
        provider.received_system_prompt
        is not None
    )


def test_generates_general_answer_without_context() -> None:
    context_builder = FakeContextBuilder()
    provider = FakeLanguageProvider()

    service = ResponseGenerationService(
        context_builder=context_builder,
        prompt_builder=PromptBuilder(),
        language_provider=provider,
    )

    answer = service.generate(
        project_id=7,
        query="Â¿QuÃ© es la gravedad?",
        current_message_id="mensaje-actual",
        include_context=False,
    )

    assert context_builder.build_calls == 0
    assert answer.document_paths == ()
    assert answer.message_ids == ()
    assert answer.context_characters == 0
    assert answer.context_truncated is False

    assert provider.received_prompt is not None
    assert "Â¿QuÃ© es la gravedad?" in (
        provider.received_prompt
    )
    assert "El proyecto utiliza SQLite" not in (
        provider.received_prompt
    )


def test_passes_context_limit() -> None:
    context_builder = FakeContextBuilder()

    service = ResponseGenerationService(
        context_builder=context_builder,
        prompt_builder=PromptBuilder(),
        language_provider=(
            FakeLanguageProvider()
        ),
        maximum_context_characters=2500,
    )

    service.generate(
        project_id=1,
        query="Consulta",
        current_message_id="mensaje",
    )

    assert (
        context_builder.received_maximum
        == 2500
    )


def test_rejects_small_context_limit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "maximum_context_characters "
            "debe ser al menos 100"
        ),
    ):
        ResponseGenerationService(
            context_builder=FakeContextBuilder(),
            prompt_builder=PromptBuilder(),
            language_provider=(
                FakeLanguageProvider()
            ),
            maximum_context_characters=99,
        )