import pytest

from app.tasks import (
    TaskClarificationResponse,
)


def create_response(
    **changes,
) -> TaskClarificationResponse:
    values = {
        "id": 1,
        "task_id": 2,
        "response_message_id": (
            "telegram:123:20"
        ),
        "questions": (
            "¿Formato de entrada?",
            "¿Formato de salida?",
        ),
        "answer": (
            "Entrada TXT y salida MP3."
        ),
        "created_at": "fecha",
    }

    values.update(changes)

    return TaskClarificationResponse(
        **values
    )


def test_creates_clarification_response() -> None:
    response = create_response()

    assert response.id == 1
    assert response.task_id == 2
    assert response.questions == (
        "¿Formato de entrada?",
        "¿Formato de salida?",
    )
    assert (
        response.answer
        == "Entrada TXT y salida MP3."
    )


def test_normalizes_response() -> None:
    response = create_response(
        response_message_id="  mensaje  ",
        questions=(
            "  ",
            " Pregunta ",
        ),
        answer="  Respuesta  ",
    )

    assert (
        response.response_message_id
        == "mensaje"
    )
    assert response.questions == (
        "Pregunta",
    )
    assert response.answer == "Respuesta"


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "id",
            0,
            "id debe ser mayor que cero",
        ),
        (
            "task_id",
            0,
            (
                "task_id debe ser "
                "mayor que cero"
            ),
        ),
        (
            "response_message_id",
            "   ",
            (
                "response_message_id "
                "no puede estar vacío"
            ),
        ),
        (
            "questions",
            (),
            (
                "questions no puede "
                "estar vacío"
            ),
        ),
        (
            "answer",
            "   ",
            (
                "answer no puede "
                "estar vacío"
            ),
        ),
    ],
)
def test_rejects_invalid_response(
    field_name,
    value,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        create_response(
            **{
                field_name: value,
            }
        )