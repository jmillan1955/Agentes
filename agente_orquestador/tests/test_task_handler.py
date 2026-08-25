import pytest

from app.routing import (
    ProvisionalTaskHandler,
    RequestKind,
    RoutingDecision,
)


def test_handles_task_without_executing_it() -> None:
    decision = RoutingDecision(
        kind=RequestKind.TASK,
        summary="Añadir un canal de correo",
        confidence=0.90,
    )

    result = (
        ProvisionalTaskHandler()
        .handle(decision)
    )

    assert (
        "PETICIÓN IDENTIFICADA COMO TAREA"
        in result.text
    )
    assert (
        "Añadir un canal de correo"
        in result.text
    )
    assert (
        "No se ha ejecutado ningún cambio"
        in result.text
    )
    assert (
        result.status
        == "pending_planning"
    )
    assert result.project_name is None


def test_includes_detected_project() -> None:
    decision = RoutingDecision(
        kind=RequestKind.TASK,
        summary=(
            "Modificar el Agente Orquestador"
        ),
        confidence=0.90,
        project_name="Agente Orquestador",
    )

    result = (
        ProvisionalTaskHandler()
        .handle(decision)
    )

    assert (
        "Proyecto: Agente Orquestador"
        in result.text
    )
    assert (
        result.project_name
        == "Agente Orquestador"
    )


def test_rejects_non_task_decision() -> None:
    decision = RoutingDecision(
        kind=RequestKind.GENERAL_QUERY,
        summary="¿Qué es SQLite?",
        confidence=0.70,
    )

    with pytest.raises(
        ValueError,
        match=(
            "solamente acepta peticiones "
            "de tipo task"
        ),
    ):
        ProvisionalTaskHandler().handle(
            decision
        )