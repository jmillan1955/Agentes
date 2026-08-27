import pytest

from app.planning import (
    PLANNING_SYSTEM_PROMPT,
    PlanningPromptBuilder,
)
from app.tasks import (
    TaskClarificationResponse,
    TaskRecord,
    TaskStatus,
)


def create_task() -> TaskRecord:
    return TaskRecord(
        id=2,
        project_id=1,
        session_id=3,
        source_message_id="telegram:123:20",
        title="Crea el proyecto puntuacion_padel",
        description=(
            "Crear una aplicación para llevar "
            "el marcador de un partido de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
        status=(
            TaskStatus.PENDING_CLARIFICATION
        ),
        missing_information=(
            "¿Qué tipo de aplicación necesitas?",
        ),
        plan=(),
        created_at="2026-08-25T08:00:00Z",
        updated_at="2026-08-25T08:00:00Z",
        authorized_at=None,
        completed_at=None,
    )


def create_response() -> (
    TaskClarificationResponse
):
    return TaskClarificationResponse(
        id=1,
        task_id=2,
        response_message_id=(
            "telegram:123:21"
        ),
        questions=(
            "¿Qué tipo de aplicación necesitas?",
            "¿Qué funciones debe incluir?",
        ),
        answer=(
            "Será una aplicación web. "
            "Debe definir equipos, registrar "
            "puntos y avisar del final de juegos, "
            "sets y partidos."
        ),
        created_at="2026-08-25T08:05:00Z",
    )


def test_builds_planning_prompt() -> None:
    prompt = PlanningPromptBuilder().build(
        task=create_task(),
        clarification_responses=(
            create_response(),
        ),
    )

    assert (
        prompt.system_prompt
        == PLANNING_SYSTEM_PROMPT
    )

    assert (
        "Crea el proyecto puntuacion_padel"
        in prompt.user_prompt
    )

    assert (
        "puntuacion_padel"
        in prompt.user_prompt
    )

    assert (
        "Será una aplicación web"
        in prompt.user_prompt
    )

    assert (
        '"technologies"'
        in prompt.user_prompt
    )

    assert (
        '"interfaces"'
        in prompt.user_prompt
    )

    assert (
        '"inputs"'
        in prompt.user_prompt
    )

    assert (
        '"outputs"'
        in prompt.user_prompt
    )

    assert (
        '"pending_decisions"'
        in prompt.user_prompt
    )


def test_includes_questions_and_answer() -> None:
    prompt = PlanningPromptBuilder().build(
        task=create_task(),
        clarification_responses=(
            create_response(),
        ),
    )

    assert (
        "¿Qué funciones debe incluir?"
        in prompt.user_prompt
    )

    assert (
        "registrar puntos"
        in prompt.user_prompt
    )

    assert (
        "No vuelvas a preguntar"
        in prompt.user_prompt
    )


def test_handles_task_without_responses() -> None:
    prompt = PlanningPromptBuilder().build(
        task=create_task(),
    )

    assert (
        "No hay aclaraciones adicionales."
        in prompt.user_prompt
    )


def test_rejects_empty_system_prompt() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "system_prompt no puede "
            "estar vacío"
        ),
    ):
        PlanningPromptBuilder(
            system_prompt="   "
        )

def test_treats_answers_as_binding_decisions() -> None:
    prompt = PlanningPromptBuilder().build(
        task=create_task(),
        clarification_responses=(
            create_response(),
        ),
    )

    assert (
        "DECISIONES CONFIRMADAS Y VINCULANTES"
        in prompt.user_prompt
    )

    assert (
        "No presentes alternativas"
        in prompt.user_prompt
    )

    assert (
        "pending_decisions debe contener "
        "solamente decisiones nuevas"
        in prompt.user_prompt
    )