from dataclasses import replace

import pytest

from app.planning import (
    PlanStatus,
    TaskPlan,
)


def create_plan(
    pending_decisions: tuple[
        str,
        ...,
    ] = (),
) -> TaskPlan:
    return TaskPlan(
        id=1,
        task_id=2,
        version=1,
        status=PlanStatus.DRAFT,
        objective=(
            "Crear una aplicación para "
            "controlar partidos de pádel"
        ),
        scope=(
            "Definir equipos y jugadores",
            "Controlar puntos, juegos y sets",
        ),
        technologies=(
            "Frontend web",
            "API REST",
            "SQLite",
        ),
        interfaces=(
            "Interfaz web adaptable a móvil",
        ),
        inputs=(
            "Botón para añadir un punto",
            "Botón para corregir un punto",
        ),
        outputs=(
            "Marcador visual",
            "Aviso de fin de juego",
            "Aviso de fin de set",
            "Aviso de fin de partido",
        ),
        data_entities=(
            "Partido",
            "Equipo",
            "Jugador",
            "Set",
            "Juego",
        ),
        business_rules=(
            "Puntuación reglamentaria de pádel",
        ),
        phases=(
            "Definir arquitectura",
            "Crear motor de puntuación",
            "Crear API",
            "Crear interfaz web",
        ),
        tests=(
            "Pruebas de puntos y juegos",
            "Pruebas de sets y partidos",
        ),
        deployment=(
            "Ejecución local inicial",
        ),
        pending_decisions=pending_decisions,
        excluded_items=(
            (
                "No se ejecutará código "
                "sin autorización"
            ),
        ),
        completion_criteria=(
            "Registrar equipos y jugadores",
            "Añadir y corregir puntos",
            (
                "Calcular automáticamente "
                "juegos, sets y partidos"
            ),
            (
                "Avisar del final de cada "
                "juego, set y partido"
            ),
        ),
        created_at="2026-08-25T08:00:00Z",
        updated_at="2026-08-25T08:00:00Z",
    )


def test_defines_plan_statuses() -> None:
    assert PlanStatus.DRAFT.value == "draft"
    assert (
        PlanStatus.PENDING_CLARIFICATION.value
        == "pending_clarification"
    )
    assert (
        PlanStatus.PENDING_APPROVAL.value
        == "pending_approval"
    )
    assert (
        PlanStatus.APPROVED.value
        == "approved"
    )
    assert (
        PlanStatus.SUPERSEDED.value
        == "superseded"
    )


def test_creates_task_plan() -> None:
    plan = create_plan()

    assert plan.id == 1
    assert plan.task_id == 2
    assert plan.version == 1
    assert plan.status == PlanStatus.DRAFT

    assert (
        plan.objective
        == (
            "Crear una aplicación para "
            "controlar partidos de pádel"
        )
    )

    assert "SQLite" in plan.technologies
    assert "Partido" in plan.data_entities
    assert len(plan.phases) == 4

    assert (
        plan.created_at
        == "2026-08-25T08:00:00Z"
    )
    assert (
        plan.updated_at
        == "2026-08-25T08:00:00Z"
    )


def test_normalizes_plan_texts() -> None:
    plan = replace(
        create_plan(),
        objective="  Crear marcador  ",
        scope=(
            "  Registrar puntos  ",
            "",
            "   ",
            " Mostrar marcador ",
        ),
        technologies=(
            "  FastAPI  ",
            "",
            " SQLite ",
        ),
    )

    assert plan.objective == "Crear marcador"

    assert plan.scope == (
        "Registrar puntos",
        "Mostrar marcador",
    )

    assert plan.technologies == (
        "FastAPI",
        "SQLite",
    )


def test_requires_clarification() -> None:
    plan = create_plan(
        pending_decisions=(
            "Decidir si se utiliza punto de oro",
            "Definir el formato del partido",
        )
    )

    assert plan.requires_clarification is True
    assert plan.can_be_approved is False


def test_does_not_require_clarification() -> None:
    plan = create_plan()

    assert plan.requires_clarification is False


def test_can_be_approved() -> None:
    plan = create_plan()

    assert plan.can_be_approved is True


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
    ),
    [
        ("scope", ()),
        ("technologies", ()),
        ("phases", ()),
        ("completion_criteria", ()),
    ],
)
def test_cannot_be_approved_without_required_sections(
    field_name: str,
    field_value: tuple[str, ...],
) -> None:
    plan = replace(
        create_plan(),
        **{
            field_name: field_value,
        },
    )

    assert plan.can_be_approved is False


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
        "expected_message",
    ),
    [
        (
            "id",
            0,
            "id debe ser mayor que cero",
        ),
        (
            "task_id",
            0,
            "task_id debe ser mayor que cero",
        ),
        (
            "version",
            0,
            "version debe ser mayor que cero",
        ),
    ],
)
def test_rejects_invalid_identifiers(
    field_name: str,
    field_value: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        replace(
            create_plan(),
            **{
                field_name: field_value,
            },
        )


def test_rejects_empty_objective() -> None:
    with pytest.raises(
        ValueError,
        match="objective no puede estar vacío",
    ):
        replace(
            create_plan(),
            objective="   ",
        )