from dataclasses import replace

from app.planning import (
    PlanStatus,
    TaskPlan,
)
from app.planning.formatter import (
    PlanningFormatter,
)
from app.tasks import (
    TaskRecord,
    TaskStatus,
)


def create_task() -> TaskRecord:
    return TaskRecord(
        id=2,
        project_id=1,
        session_id=3,
        source_message_id="mensaje",
        title="Crear puntuacion_padel",
        description=(
            "Crear una aplicación de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
        status=(
            TaskStatus.PENDING_CLARIFICATION
        ),
        missing_information=(
            "¿Se utilizará punto de oro?",
        ),
        plan=(),
        created_at="2026-08-25T08:00:00Z",
        updated_at="2026-08-25T08:00:00Z",
        authorized_at=None,
        completed_at=None,
    )


def create_plan() -> TaskPlan:
    return TaskPlan(
        id=1,
        task_id=2,
        version=1,
        status=(
            PlanStatus.PENDING_CLARIFICATION
        ),
        objective=(
            "Controlar el marcador "
            "de partidos de pádel"
        ),
        scope=(
            "Definir equipos y jugadores",
            "Registrar puntos",
        ),
        technologies=(
            "Angular",
            "FastAPI",
            "SQLite",
        ),
        interfaces=(
            "Aplicación web móvil",
            "API REST",
        ),
        inputs=(
            "Añadir punto",
            "Corregir punto",
        ),
        outputs=(
            "Marcador visual",
            "Avisos de finalización",
        ),
        data_entities=(
            "Partido",
            "Equipo",
            "Jugador",
        ),
        business_rules=(
            "Puntuación reglamentaria",
        ),
        phases=(
            "Crear motor de puntuación",
            "Crear API",
            "Crear interfaz web",
        ),
        tests=(
            "Probar puntos, juegos y sets",
        ),
        deployment=(
            "Ejecución local inicial",
        ),
        pending_decisions=(
            "¿Se utilizará punto de oro?",
            "¿Cuántos sets tendrá el partido?",
        ),
        excluded_items=(
            "No ejecutar sin autorización",
        ),
        completion_criteria=(
            "Registrar un partido",
            "Calcular el resultado",
        ),
        created_at="2026-08-25T08:00:00Z",
        updated_at="2026-08-25T08:00:00Z",
    )


def test_formats_complete_plan() -> None:
    text = PlanningFormatter().format(
        plan=create_plan(),
        task=create_task(),
    )

    assert (
        "PLAN PROPUESTO — VERSIÓN 1"
        in text
    )
    assert "Proyecto: puntuacion_padel" in text
    assert "TECNOLOGÍAS PROPUESTAS" in text
    assert "- Angular" in text
    assert "INTERFACES" in text
    assert "ENTRADAS" in text
    assert "SALIDAS" in text
    assert "DECISIONES PENDIENTES" in text
    assert (
        "/responder 2 <tus aclaraciones>"
        in text
    )
    assert (
        "No se ha creado ni modificado "
        "código del proyecto."
        in text
    )


def test_numbers_phases_and_decisions() -> None:
    text = PlanningFormatter().format(
        plan=create_plan(),
        task=create_task(),
    )

    assert (
        "1. Crear motor de puntuación"
        in text
    )
    assert (
        "1. ¿Se utilizará punto de oro?"
        in text
    )
    assert (
        "2. ¿Cuántos sets tendrá el partido?"
        in text
    )


def test_formats_plan_ready_for_approval() -> None:
    plan = replace(
        create_plan(),
        status=PlanStatus.PENDING_APPROVAL,
        pending_decisions=(),
    )

    text = PlanningFormatter().format(
        plan=plan,
        task=create_task(),
    )

    assert (
        "pendiente de aprobación"
        in text
    )
    assert (
        "no tiene decisiones bloqueantes"
        in text
    )
    assert (
        "preparada para solicitar aprobación"
        in text
    )
    assert "/responder" not in text