import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskRepository,
)
from app.tasks import (
    InvalidTaskTransitionError,
    TaskStatus,
)


def create_context(
    database: ContextDatabase,
) -> tuple[int, int]:
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
        user_id="123456",
        conversation_id="654321",
    )

    return project.id, session.id


def create_task(
    repository: TaskRepository,
    project_id: int,
    session_id: int,
    source_message_id: str = (
        "telegram:654321:1"
    ),
    status: TaskStatus = (
        TaskStatus.PENDING_PLANNING
    ),
):
    return repository.create(
        project_id=project_id,
        session_id=session_id,
        source_message_id=(
            source_message_id
        ),
        title="Crear agente_audioText",
        description=(
            "Crear un proyecto para convertir "
            "texto en audio"
        ),
        target_project_name=(
            "agente_audioText"
        ),
        status=status,
    )


def test_creates_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        assert task.id > 0
        assert task.project_id == project_id
        assert task.session_id == session_id
        assert (
            task.status
            == TaskStatus.PENDING_PLANNING
        )
        assert (
            task.target_project_name
            == "agente_audioText"
        )


def test_persists_task_collections() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        task = TaskRepository(
            database
        ).create(
            project_id=project_id,
            session_id=session_id,
            source_message_id=(
                "telegram:654321:2"
            ),
            title="Crear agente",
            description="Descripción",
            missing_information=(
                "Formato de entrada",
                "Formato de salida",
            ),
            plan=(
                "Crear estructura",
                "Crear pruebas",
            ),
        )

        assert task.missing_information == (
            "Formato de entrada",
            "Formato de salida",
        )
        assert task.plan == (
            "Crear estructura",
            "Crear pruebas",
        )


def test_is_idempotent_for_source_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        first = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        second = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        assert second.id == first.id

        rows = database.connection.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        assert rows == 1


def test_returns_none_for_unknown_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = TaskRepository(
            database
        )

        assert (
            repository.get_by_id(999)
            is None
        )


def test_lists_tasks_by_status() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
            source_message_id="mensaje-1",
            status=(
                TaskStatus.PENDING_PLANNING
            ),
        )

        create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
            source_message_id="mensaje-2",
            status=(
                TaskStatus.PENDING_APPROVAL
            ),
        )

        pending = repository.list_by_project(
            project_id=project_id,
            status=(
                TaskStatus.PENDING_PLANNING
            ),
        )

        all_tasks = repository.list_by_project(
            project_id=project_id
        )

        assert len(pending) == 1
        assert (
            pending[0].status
            == TaskStatus.PENDING_PLANNING
        )
        assert len(all_tasks) == 2


def test_rejects_session_from_other_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        first_project = ProjectRepository(
            database
        ).save(
            name="Proyecto 1",
            root_path="proyecto-1",
        )

        second_project = ProjectRepository(
            database
        ).save(
            name="Proyecto 2",
            root_path="proyecto-2",
        )

        session = SessionRepository(
            database
        ).get_or_create_active(
            project_id=first_project.id,
            channel="telegram",
            user_id="usuario",
            conversation_id="conversacion",
        )

        repository = TaskRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match=(
                "La sesión no pertenece "
                "al proyecto"
            ),
        ):
            create_task(
                repository=repository,
                project_id=second_project.id,
                session_id=session.id,
            )


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        (
            "source_message_id",
            (
                "source_message_id no puede "
                "estar vacío"
            ),
        ),
        (
            "title",
            "title no puede estar vacío",
        ),
        (
            "description",
            (
                "description no puede "
                "estar vacía"
            ),
        ),
    ],
)
def test_rejects_empty_required_text(
    field_name: str,
    message: str,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        values = {
            "source_message_id": "mensaje",
            "title": "Título",
            "description": "Descripción",
        }

        values[field_name] = "   "

        with pytest.raises(
            ValueError,
            match=message,
        ):
            TaskRepository(
                database
            ).create(
                project_id=project_id,
                session_id=session_id,
                source_message_id=(
                    values[
                        "source_message_id"
                    ]
                ),
                title=values["title"],
                description=(
                    values["description"]
                ),
            )

def test_sets_missing_information() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        updated = (
            repository
            .set_missing_information(
                task_id=task.id,
                missing_information=(
                    "Formato de entrada",
                    "Formato de salida",
                ),
            )
        )

        assert (
            updated.status
            == TaskStatus.PENDING_CLARIFICATION
        )
        assert updated.missing_information == (
            "Formato de entrada",
            "Formato de salida",
        )


def test_returns_task_to_planning() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        clarification = (
            repository
            .set_missing_information(
                task_id=task.id,
                missing_information=(
                    "Formato de entrada",
                ),
            )
        )

        updated = (
            repository.return_to_planning(
                clarification.id
            )
        )

        assert (
            updated.status
            == TaskStatus.PENDING_PLANNING
        )


def test_sets_plan_and_requires_approval() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        updated = repository.set_plan(
            task_id=task.id,
            plan=(
                "Crear estructura",
                "Crear conversor",
                "Ejecutar pruebas",
            ),
        )

        assert (
            updated.status
            == TaskStatus.PENDING_APPROVAL
        )
        assert updated.requires_approval
        assert updated.plan == (
            "Crear estructura",
            "Crear conversor",
            "Ejecutar pruebas",
        )


def test_approves_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        planned = repository.set_plan(
            task_id=task.id,
            plan=("Crear proyecto",),
        )

        approved = repository.approve(
            planned.id
        )

        assert (
            approved.status
            == TaskStatus.APPROVED
        )
        assert approved.authorized_at is not None


def test_cancels_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        cancelled = repository.cancel(
            task.id
        )

        assert (
            cancelled.status
            == TaskStatus.CANCELLED
        )
        assert cancelled.completed_at is not None
        assert cancelled.is_terminal


def test_rejects_invalid_persistent_transition() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project_id, session_id = (
            create_context(database)
        )

        repository = TaskRepository(
            database
        )

        task = create_task(
            repository=repository,
            project_id=project_id,
            session_id=session_id,
        )

        with pytest.raises(
            InvalidTaskTransitionError,
            match="No se permite cambiar",
        ):
            repository.transition(
                task_id=task.id,
                target_status=(
                    TaskStatus.COMPLETED
                ),
            )


def test_rejects_unknown_task_transition() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = TaskRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match="No existe la tarea #999",
        ):
            repository.approve(999)            