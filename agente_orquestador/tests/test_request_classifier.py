import pytest

from app.routing import (
    ProviderPreference,
    RequestClassifier,
    RequestKind,
    RequestSubtype,
)


def test_classifies_command() -> None:
    decision = RequestClassifier().classify(
        "/contexto"
    )

    assert decision.kind == RequestKind.COMMAND
    assert decision.confidence == 1.0
    assert decision.subtype == RequestSubtype.COMMAND
    assert (
        decision.provider
        == ProviderPreference.INTERNAL
    )


def test_classifies_general_query() -> None:
    decision = RequestClassifier().classify(
        "¿Qué es SQLite?"
    )

    assert (
        decision.kind
        == RequestKind.GENERAL_QUERY
    )
    assert decision.project_name is None
    assert (
        decision.subtype
        == RequestSubtype.GENERAL_RESPONSE
    )


def test_classifies_project_query() -> None:
    decision = RequestClassifier().classify(
        "¿Dónde guarda el proyecto su contexto?"
    )

    assert (
        decision.kind
        == RequestKind.PROJECT_QUERY
    )
    assert (
        decision.project_name
        == "Agente Orquestador"
    )
    assert (
        decision.subtype
        == RequestSubtype.PROJECT_INFORMATION
    )


def test_classifies_task() -> None:
    decision = RequestClassifier().classify(
        "Añade un canal de entrada por correo"
    )

    assert decision.kind == RequestKind.TASK
    assert decision.confidence == 0.90


def test_classifies_project_task() -> None:
    decision = RequestClassifier().classify(
        "Modifica el Agente Orquestador"
    )

    assert decision.kind == RequestKind.TASK
    assert (
        decision.project_name
        == "Agente Orquestador"
    )


def test_normalizes_accents() -> None:
    decision = RequestClassifier().classify(
        "Créa una prueba nueva"
    )

    assert decision.kind == RequestKind.TASK


def test_rejects_empty_text() -> None:
    with pytest.raises(
        ValueError,
        match="text no puede estar vacío",
    ):
        RequestClassifier().classify("   ")


def test_detects_named_project() -> None:
    decision = RequestClassifier().classify(
        "Crea el proyecto agente_audioText"
    )

    assert decision.kind == RequestKind.TASK
    assert (
        decision.project_name
        == "agente_audioText"
    )


def test_classifies_task_after_named_project_preamble() -> None:
    decision = RequestClassifier().classify(
        (
            "En el proyecto calculadora_tkinter, "
            "crea una calculadora visual"
        )
    )

    assert decision.kind == RequestKind.TASK
    assert (
        decision.project_name
        == "calculadora_tkinter"
    )


@pytest.mark.parametrize(
    ("text", "provider"),
    [
        (
            "Pregunta a Ollama qué es pytest",
            ProviderPreference.OLLAMA,
        ),
        (
            "Pregunta a OpenAI qué es pytest",
            ProviderPreference.OPENAI,
        ),
        (
            "Pregunta a Codex qué es pytest",
            ProviderPreference.CODEX,
        ),
    ],
)
def test_detects_explicit_provider_for_short_response(
    text: str,
    provider: ProviderPreference,
) -> None:
    decision = RequestClassifier().classify(text)

    assert (
        decision.kind
        == RequestKind.GENERAL_QUERY
    )
    assert (
        decision.subtype
        == RequestSubtype.PROVIDER_RESPONSE
    )
    assert decision.provider == provider


def test_classifies_provider_comparison() -> None:
    decision = RequestClassifier().classify(
        "Compara Ollama y OpenAI"
    )

    assert (
        decision.subtype
        == RequestSubtype.PROVIDER_COMPARISON
    )
    assert (
        decision.provider
        == ProviderPreference.COMPARISON
    )


def test_classifies_current_information_for_verification(
) -> None:
    decision = RequestClassifier().classify(
        "¿Cuál es la versión estable actual "
        "de Home Assistant?"
    )

    assert (
        decision.subtype
        == RequestSubtype.CURRENT_INFORMATION
    )
    assert (
        decision.provider
        == ProviderPreference.VERIFICATION
    )


@pytest.mark.parametrize(
    ("text", "subtype"),
    [
        (
            "Crea un script Python que renombre "
            "archivos y añade pruebas",
            RequestSubtype.PYTHON_SCRIPT,
        ),
        (
            "En el proyecto calculadora, crea "
            "una aplicación de escritorio para "
            "Windows con Python y Tkinter",
            RequestSubtype.DESKTOP_PYTHON_APP,
        ),
        (
            "Crea una automatización YAML para "
            "Home Assistant",
            RequestSubtype.HOME_ASSISTANT_YAML,
        ),
        (
            "Crea una API REST con FastAPI y "
            "SQLite",
            RequestSubtype.BACKEND_API,
        ),
        (
            "Corrige el error de pytest en "
            "calculator_engine.py",
            RequestSubtype.BUG_FIX,
        ),
    ],
)
def test_classifies_task_subtypes(
    text: str,
    subtype: RequestSubtype,
) -> None:
    decision = RequestClassifier().classify(text)

    assert decision.kind == RequestKind.TASK
    assert decision.subtype == subtype


def test_routes_code_repair_requested_from_codex(
) -> None:
    decision = RequestClassifier().classify(
        "Corrige con Codex el fallo de pytest "
        "del proyecto calculadora"
    )

    assert decision.kind == RequestKind.TASK
    assert decision.subtype == RequestSubtype.BUG_FIX
    assert (
        decision.provider
        == ProviderPreference.CODEX
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hola",
        "Buenos días",
        "Gracias",
    ],
)
def test_classifies_social_messages(
    text: str,
) -> None:
    decision = RequestClassifier().classify(text)

    assert (
        decision.subtype
        == RequestSubtype.SOCIAL
    )

def test_pytest_requirement_does_not_turn_script_into_bug_fix(
) -> None:
    decision = RequestClassifier().classify(
        "Crea un script Python que renombre "
        "todos los archivos JPG de una carpeta, "
        "conserve su extensión y tenga pruebas "
        "con pytest"
    )

    assert decision.kind == RequestKind.TASK
    assert (
        decision.subtype
        == RequestSubtype.PYTHON_SCRIPT
    )
