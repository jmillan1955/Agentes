import pytest

from app.routing import (
    RequestClassifier,
    RequestKind,
)


def test_classifies_command() -> None:
    decision = RequestClassifier().classify(
        "/contexto"
    )

    assert decision.kind == RequestKind.COMMAND
    assert decision.confidence == 1.0


def test_classifies_general_query() -> None:
    decision = RequestClassifier().classify(
        "¿Qué es SQLite?"
    )

    assert (
        decision.kind
        == RequestKind.GENERAL_QUERY
    )
    assert decision.project_name is None


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
