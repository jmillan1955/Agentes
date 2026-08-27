import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskApprovalRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.planning import PlanStatus
from app.tasks import TaskStatus


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
        user_id="8288969559",
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
            "Crear una aplicacion para "
            "controlar partidos de padel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )


def create_plan(
    database: ContextDatabase,
    task_id: int,
    pending_decisions: tuple[
        str,
        ...,
    ] = (),
):
    return TaskPlanRepository(
        database
    ).create(
        task_id=task_id,
        objective=(
            "Controlar el marcador "
            "de partidos de padel"
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
            "Interfaz web movil",
            "API REST",
        ),
        inputs=(
            "Anadir punto",
            "Corregir punto",
        ),
        outputs=(
            "Marcador visual",
            "Avisos de finalizacion",
        ),
        data_entities=(
            "Partido",
            "Equipo",
            "Jugador",
        ),
        business_rules=(
            "Puntuacion reglamentaria",
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
            "Ejecucion local inicial",
        ),
        pending_decisions=(
            pending_decisions
        ),
        excluded_items=(
            "No ejecutar sin autorizacion",
        ),
        completion_criteria=(
            "Registrar un partido",
            "Calcular el resultado",
        ),
    )


def prepare_task_for_approval(
    database: ContextDatabase,
):
    task = create_task(database)

    plan = create_plan(
        database=database,
        task_id=task.id,
    )

    task = TaskRepository(
        database
    ).set_plan(
        task_id=task.id,
        plan=plan.phases,
    )

    return task, plan


def test_approves_task_plan_and_authorization() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = (
            prepare_task_for_approval(
                database
            )
        )

        approval = TaskApprovalRepository(
            database
        ).approve(
            task_id=task.id,
            plan_id=plan.id,
            plan_version=plan.version,
            authorized_user_id="8288969559",
            authorization_message_id=(
                "telegram:chat:100"
            ),
            channel="telegram",
        )

        stored_task = TaskRepository(
            database
        ).get_by_id(task.id)

        stored_plan = TaskPlanRepository(
            database
        ).get_by_id(plan.id)

        assert approval.id > 0
        assert approval.task_id == task.id
        assert approval.plan_id == plan.id
        assert (
            approval.plan_version
            == plan.version
        )
        assert (
            approval.authorized_user_id
            == "8288969559"
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.APPROVED
        )
        assert (
            stored_task.authorized_at
            is not None
        )

        assert stored_plan is not None
        assert (
            stored_plan.status
            == PlanStatus.APPROVED
        )


def test_gets_approval_by_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = (
            prepare_task_for_approval(
                database
            )
        )

        repository = TaskApprovalRepository(
            database
        )

        created = repository.approve(
            task_id=task.id,
            plan_id=plan.id,
            plan_version=plan.version,
            authorized_user_id="8288969559",
            authorization_message_id=(
                "telegram:chat:101"
            ),
            channel="telegram",
        )

        stored = repository.get_by_task_id(
            task.id
        )

        assert stored == created


def test_approval_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = (
            prepare_task_for_approval(
                database
            )
        )

        repository = TaskApprovalRepository(
            database
        )

        first = repository.approve(
            task_id=task.id,
            plan_id=plan.id,
            plan_version=plan.version,
            authorized_user_id="8288969559",
            authorization_message_id=(
                "telegram:chat:102"
            ),
            channel="telegram",
        )

        second = repository.approve(
            task_id=task.id,
            plan_id=plan.id,
            plan_version=plan.version,
            authorized_user_id="8288969559",
            authorization_message_id=(
                "telegram:chat:102"
            ),
            channel="telegram",
        )

        count = database.connection.execute(
            """
            SELECT COUNT(*)
            FROM task_approvals
            WHERE task_id = ?
            """,
            (task.id,),
        ).fetchone()[0]

        assert second == first
        assert count == 1


def test_rejects_superseded_plan() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        first_plan = create_plan(
            database=database,
            task_id=task.id,
        )

        latest_plan = create_plan(
            database=database,
            task_id=task.id,
        )

        TaskRepository(
            database
        ).set_plan(
            task_id=task.id,
            plan=latest_plan.phases,
        )

        repository = TaskApprovalRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match=(
                "Solo se puede aprobar "
                "la ultima version"
            ),
        ):
            repository.approve(
                task_id=task.id,
                plan_id=first_plan.id,
                plan_version=(
                    first_plan.version
                ),
                authorized_user_id=(
                    "8288969559"
                ),
                authorization_message_id=(
                    "telegram:chat:103"
                ),
                channel="telegram",
            )

        assert (
            repository.get_by_task_id(
                task.id
            )
            is None
        )


def test_rejects_plan_with_pending_decisions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        plan = create_plan(
            database=database,
            task_id=task.id,
            pending_decisions=(
                "Decidir el punto de oro",
            ),
        )

        TaskRepository(
            database
        ).set_plan(
            task_id=task.id,
            plan=plan.phases,
        )

        repository = TaskApprovalRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match=(
                "El plan no esta pendiente "
                "de aprobacion"
            ),
        ):
            repository.approve(
                task_id=task.id,
                plan_id=plan.id,
                plan_version=plan.version,
                authorized_user_id=(
                    "8288969559"
                ),
                authorization_message_id=(
                    "telegram:chat:104"
                ),
                channel="telegram",
            )

        stored_task = TaskRepository(
            database
        ).get_by_id(task.id)

        stored_plan = TaskPlanRepository(
            database
        ).get_by_id(plan.id)

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.PENDING_APPROVAL
        )

        assert stored_plan is not None
        assert (
            stored_plan.status
            == PlanStatus.PENDING_CLARIFICATION
        )

        assert (
            repository.get_by_task_id(
                task.id
            )
            is None
        )


def test_rejects_incorrect_plan_version() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = (
            prepare_task_for_approval(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "La version del plan "
                "no coincide"
            ),
        ):
            TaskApprovalRepository(
                database
            ).approve(
                task_id=task.id,
                plan_id=plan.id,
                plan_version=(
                    plan.version + 1
                ),
                authorized_user_id=(
                    "8288969559"
                ),
                authorization_message_id=(
                    "telegram:chat:105"
                ),
                channel="telegram",
            )