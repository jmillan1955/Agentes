import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.planning import PlanStatus


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

    return TaskRepository(
        database
    ).create(
        project_id=project.id,
        session_id=session.id,
        source_message_id="mensaje-tarea",
        title="Crear puntuacion_padel",
        description=(
            "Crear una aplicación para "
            "controlar partidos de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )


def create_plan(
    repository: TaskPlanRepository,
    task_id: int,
    pending_decisions: tuple[
        str,
        ...,
    ] = (),
):
    return repository.create(
        task_id=task_id,
        objective=(
            "Controlar el marcador "
            "de partidos de pádel"
        ),
        scope=(
            "Definir equipos",
            "Registrar puntos",
        ),
        technologies=(
            "Frontend web",
            "FastAPI",
            "SQLite",
        ),
        interfaces=(
            "Interfaz web móvil",
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
            "Probar juegos y sets",
        ),
        deployment=(
            "Ejecución local inicial",
        ),
        pending_decisions=(
            pending_decisions
        ),
        excluded_items=(
            "No ejecutar sin autorización",
        ),
        completion_criteria=(
            "Registrar un partido",
            "Calcular el resultado",
        ),
    )


def test_creates_first_plan_version() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = TaskPlanRepository(
            database
        )

        plan = create_plan(
            repository=repository,
            task_id=task.id,
            pending_decisions=(
                "Decidir el punto de oro",
            ),
        )

        assert plan.id > 0
        assert plan.task_id == task.id
        assert plan.version == 1
        assert (
            plan.status
            == PlanStatus.PENDING_CLARIFICATION
        )
        assert plan.requires_clarification
        assert "FastAPI" in plan.technologies


def test_plan_without_pending_decisions_waits_for_approval() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        plan = create_plan(
            repository=TaskPlanRepository(
                database
            ),
            task_id=task.id,
        )

        assert (
            plan.status
            == PlanStatus.PENDING_APPROVAL
        )
        assert plan.can_be_approved


def test_creates_consecutive_versions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = TaskPlanRepository(
            database
        )

        first = create_plan(
            repository=repository,
            task_id=task.id,
            pending_decisions=(
                "Decidir el punto de oro",
            ),
        )

        second = create_plan(
            repository=repository,
            task_id=task.id,
            pending_decisions=(
                "Decidir el desempate",
            ),
        )

        refreshed_first = repository.get_by_id(
            first.id
        )

        assert second.version == 2
        assert refreshed_first is not None
        assert (
            refreshed_first.status
            == PlanStatus.SUPERSEDED
        )

        assert (
            repository.get_latest(task.id)
            == second
        )


def test_lists_all_plan_versions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        repository = TaskPlanRepository(
            database
        )

        create_plan(
            repository=repository,
            task_id=task.id,
        )

        create_plan(
            repository=repository,
            task_id=task.id,
        )

        plans = repository.list_by_task(
            task.id
        )

        assert len(plans) == 2
        assert [
            plan.version
            for plan in plans
        ] == [1, 2]


def test_rejects_unknown_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = TaskPlanRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match="No existe la tarea",
        ):
            create_plan(
                repository=repository,
                task_id=999,
            )