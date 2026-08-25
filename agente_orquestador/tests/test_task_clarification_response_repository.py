import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskClarificationResponseRepository,
    TaskRepository,
)
from app.tasks import TaskStatus


QUESTIONS = (
    "¿Cuál es el objetivo del proyecto?",
    "¿Qué interfaz debe utilizar?",
)


def create_task(
    database: ContextDatabase,
):
    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    session = SessionRepository(
        database
    ).get_or_create_active(
        project_id=project.id,
        channel="telegram",
        user_id="usuario",
        conversation_id="conversacion",
    )

    repository = TaskRepository(database)

    task = repository.create(
        project_id=project.id,
        session_id=session.id,
        source_message_id="mensaje-tarea-1",
        title="Crear puntuacion_padel",
        description=(
            "Crear una aplicación para "
            "controlar partidos de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )

    return repository.set_missing_information(
        task_id=task.id,
        missing_information=QUESTIONS,
    )


def test_creates_clarification_response() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        response = repository.create(
            task_id=task.id,
            response_message_id=(
                "telegram:123:10"
            ),
            questions=task.missing_information,
            answer=(
                "Será una aplicación web "
                "adaptada al móvil."
            ),
        )

        assert response.id > 0
        assert response.task_id == task.id
        assert (
            response.response_message_id
            == "telegram:123:10"
        )
        assert response.questions == QUESTIONS
        assert (
            response.answer
            == (
                "Será una aplicación web "
                "adaptada al móvil."
            )
        )
        assert response.created_at


def test_creation_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        first = repository.create(
            task_id=task.id,
            response_message_id="mensaje-10",
            questions=task.missing_information,
            answer="Aplicación web.",
        )

        second = repository.create(
            task_id=task.id,
            response_message_id="mensaje-10",
            questions=task.missing_information,
            answer="Texto repetido.",
        )

        assert second.id == first.id
        assert (
            second.answer
            == "Aplicación web."
        )


def test_lists_responses_by_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        repository.create(
            task_id=task.id,
            response_message_id="mensaje-10",
            questions=task.missing_information,
            answer="Primera respuesta.",
        )

        repository.create(
            task_id=task.id,
            response_message_id="mensaje-11",
            questions=task.missing_information,
            answer="Segunda respuesta.",
        )

        responses = repository.list_by_task(
            task.id
        )

        assert len(responses) == 2
        assert (
            responses[0].answer
            == "Primera respuesta."
        )
        assert (
            responses[1].answer
            == "Segunda respuesta."
        )


def test_rejects_unknown_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match="No existe la tarea",
        ):
            repository.create(
                task_id=999,
                response_message_id="mensaje",
                questions=QUESTIONS,
                answer="Respuesta",
            )


def test_rejects_task_not_waiting_for_clarification() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project = ProjectRepository(
            database
        ).save(
            name="Agente Orquestador",
            root_path="ruta-del-proyecto",
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=project.id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        task = TaskRepository(
            database
        ).create(
            project_id=project.id,
            session_id=session.id,
            source_message_id="mensaje-tarea",
            title="Crear proyecto",
            description="Crear proyecto",
            status=(
                TaskStatus.PENDING_PLANNING
            ),
        )

        repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "no está pendiente "
                "de aclaración"
            ),
        ):
            repository.create(
                task_id=task.id,
                response_message_id="mensaje",
                questions=QUESTIONS,
                answer="Respuesta",
            )