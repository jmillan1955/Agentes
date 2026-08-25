import pytest

from app.routing import (
    ProvisionalTaskHandler,
    RequestKind,
    RoutingDecision,
)
from app.tasks import (
    TaskRecord,
    TaskStatus,
)


def create_decision() -> RoutingDecision:
    return RoutingDecision(
        kind=RequestKind.TASK,
        summary="Añadir un canal de correo",
        confidence=0.90,
        project_name="agente_audioText",
    )


def create_task(
    status: TaskStatus = (
        TaskStatus.PENDING_PLANNING
    ),
    missing_information: tuple[
        str,
        ...,
    ] = (),
) -> TaskRecord:
    return TaskRecord(
        id=1,
        project_id=1,
        session_id=1,
        source_message_id="mensaje-1",
        title="Crear agente_audioText",
        description=(
            "Crear agente_audioText"
        ),
        target_project_name=(
            "agente_audioText"
        ),
        status=status,
        missing_information=(
            missing_information
        ),
        plan=(),
        created_at="fecha",
        updated_at="fecha",
        authorized_at=None,
        completed_at=None,
    )


def test_handles_task_without_executing_it() -> None:
    result = (
        ProvisionalTaskHandler()
        .handle(
            decision=create_decision(),
            task=create_task(),
        )
    )

    assert (
        "PETICIÓN IDENTIFICADA COMO TAREA"
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
    assert (
        result.project_name
        == "agente_audioText"
    )


def test_includes_detected_project() -> None:
    result = (
        ProvisionalTaskHandler()
        .handle(
            decision=create_decision(),
            task=create_task(),
        )
    )

    assert (
        "Proyecto: agente_audioText"
        in result.text
    )


def test_includes_clarification_questions() -> None:
    result = (
        ProvisionalTaskHandler()
        .handle(
            decision=create_decision(),
            task=create_task(
                status=(
                    TaskStatus
                    .PENDING_CLARIFICATION
                ),
                missing_information=(
                    "¿Qué formato de entrada?",
                    "¿Qué formato de salida?",
                ),
            ),
        )
    )

    assert (
        "Estado: pendiente de aclaraciones"
        in result.text
    )
    assert (
        "1. ¿Qué formato de entrada?"
        in result.text
    )
    assert (
        "2. ¿Qué formato de salida?"
        in result.text
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
            decision=decision,
            task=create_task(),
        )