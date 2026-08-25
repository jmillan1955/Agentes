import pytest

from app.routing import (
    RequestKind,
    RoutingDecision,
)


def test_creates_general_query_decision() -> None:
    decision = RoutingDecision(
        kind=RequestKind.GENERAL_QUERY,
        summary="Explicar qué es SQLite",
        confidence=0.95,
    )

    assert (
        decision.kind
        == RequestKind.GENERAL_QUERY
    )
    assert (
        decision.summary
        == "Explicar qué es SQLite"
    )
    assert decision.confidence == 0.95
    assert decision.project_name is None
    assert not decision.requires_clarification


def test_creates_project_task_decision() -> None:
    decision = RoutingDecision(
        kind=RequestKind.TASK,
        summary=(
            "Añadir entrada de audio "
            "al Agente Orquestador"
        ),
        confidence=0.90,
        project_name="Agente Orquestador",
    )

    assert decision.kind == RequestKind.TASK
    assert (
        decision.project_name
        == "Agente Orquestador"
    )
    assert not decision.requires_clarification


def test_detects_missing_information() -> None:
    decision = RoutingDecision(
        kind=RequestKind.CLARIFICATION,
        summary="Crear una aplicación web",
        confidence=0.75,
        missing_information=(
            "Tecnología del backend",
            "Tipo de base de datos",
        ),
    )

    assert decision.requires_clarification
    assert decision.missing_information == (
        "Tecnología del backend",
        "Tipo de base de datos",
    )


def test_normalizes_text_values() -> None:
    decision = RoutingDecision(
        kind=RequestKind.PROJECT_QUERY,
        summary="  Consultar el contexto  ",
        confidence=0.80,
        project_name="  Agente Orquestador  ",
        missing_information=(
            "  ",
            " Nombre del documento ",
        ),
    )

    assert (
        decision.summary
        == "Consultar el contexto"
    )
    assert (
        decision.project_name
        == "Agente Orquestador"
    )
    assert decision.missing_information == (
        "Nombre del documento",
    )


@pytest.mark.parametrize(
    "confidence",
    [-0.01, 1.01],
)
def test_rejects_invalid_confidence(
    confidence: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "confidence debe estar "
            "entre 0 y 1"
        ),
    ):
        RoutingDecision(
            kind=RequestKind.GENERAL_QUERY,
            summary="Consulta",
            confidence=confidence,
        )


def test_rejects_empty_summary() -> None:
    with pytest.raises(
        ValueError,
        match="summary no puede estar vacío",
    ):
        RoutingDecision(
            kind=RequestKind.GENERAL_QUERY,
            summary="   ",
            confidence=0.5,
        )