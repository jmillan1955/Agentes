import pytest

from app.context import ContextBlock
from app.prompt_builder import (
    DEFAULT_SYSTEM_PROMPT,
    PromptBuilder,
)


def create_context(
    text: str = (
        "El proyecto utiliza SQLite "
        "para almacenar el contexto."
    ),
) -> ContextBlock:
    return ContextBlock(
        query="¿Dónde se almacena el contexto?",
        text=text,
        document_paths=(
            "docs/contexto.md",
        ),
        message_ids=(),
        total_characters=len(text),
        truncated=False,
    )


def test_builds_prompt_with_context() -> None:
    builder = PromptBuilder()

    package = builder.build(
        query=(
            "¿Dónde se almacena "
            "el contexto?"
        ),
        context=create_context(),
    )

    assert (
        package.system_prompt
        == DEFAULT_SYSTEM_PROMPT
    )
    assert "INICIO DEL CONTEXTO" in (
        package.user_prompt
    )
    assert (
        "El proyecto utiliza SQLite"
        in package.user_prompt
    )
    assert (
        "PETICIÓN DEL USUARIO"
        in package.user_prompt
    )
    assert package.user_prompt.endswith(
        "¿Dónde se almacena el contexto?"
    )


def test_keeps_query_outside_context() -> None:
    builder = PromptBuilder()

    package = builder.build(
        query="Explica el Hito 4",
        context=create_context(
            "Hito 4: búsqueda relevante"
        ),
    )

    context_end = package.user_prompt.index(
        "FIN DEL CONTEXTO"
    )
    query_position = (
        package.user_prompt.rindex(
            "Explica el Hito 4"
        )
    )

    assert query_position > context_end


def test_rejects_empty_query() -> None:
    builder = PromptBuilder()

    with pytest.raises(
        ValueError,
        match="query no puede estar vacía",
    ):
        builder.build(
            query="   ",
            context=create_context(),
        )


def test_rejects_empty_system_prompt() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "system_prompt no puede "
            "estar vacío"
        ),
    ):
        PromptBuilder(
            system_prompt="   "
        )