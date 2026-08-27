import pytest

from app.approvals.service import (
    ApprovalPermissionError,
    ApprovalService,
    ApprovalValidationError,
)
from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskApprovalRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.planning import (
    PlanStatus,
)
from app.tasks import (
    TaskStatus,
)


APPROVER_USER_ID = "8288969559"


def create_task_and_plan(
    database: ContextDatabase,
    pending_decisions: tuple[
        str,
        ...,
    ] = (),
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
        user_id=APPROVER_USER_ID,
        conversation_id="conversacion",
    )

    task_repository = TaskRepository(
        database
    )

    plan_repository = TaskPlanRepository(
        database
    )

    task = task_repository.create(
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

    plan = plan_repository.create(
        task_id=task.id,
        objective=(
            "Crear una aplicacion para "
            "controlar partidos de padel"
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

    task = task_repository.set_plan(
        task_id=task.id,
        plan=plan.phases,
    )

    return task, plan


def create_service(
    database: ContextDatabase,
) -> ApprovalService:
    return ApprovalService(
        task_repository=TaskRepository(
            database
        ),
        plan_repository=TaskPlanRepository(
            database
        ),
        approval_repository=(
            TaskApprovalRepository(
                database
            )
        ),
        approver_user_ids=(
            int(APPROVER_USER_ID),
        ),
    )


def test_approves_latest_plan() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = create_task_and_plan(
            database
        )

        result = create_service(
            database
        ).approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:200"
            ),
            channel="telegram",
        )

        assert not result.already_approved

        assert (
            result.task.status
            == TaskStatus.APPROVED
        )
        assert (
            result.plan.status
            == PlanStatus.APPROVED
        )

        assert (
            result.approval.plan_id
            == plan.id
        )
        assert (
            result.approval.plan_version
            == plan.version
        )
        assert (
            result.approval
            .authorized_user_id
            == APPROVER_USER_ID
        )


def test_rejects_unauthorized_user() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        service = create_service(database)

        with pytest.raises(
            ApprovalPermissionError,
            match=(
                "No tienes permiso"
            ),
        ):
            service.approve(
                task_id=task.id,
                authorized_user_id=(
                    "177448510"
                ),
                authorization_message_id=(
                    "telegram:chat:201"
                ),
                channel="telegram",
            )

        stored_task = TaskRepository(
            database
        ).get_by_id(task.id)

        stored_approval = (
            TaskApprovalRepository(
                database
            ).get_by_task_id(task.id)
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.PENDING_APPROVAL
        )
        assert stored_approval is None


def test_rejects_unknown_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        service = create_service(database)

        with pytest.raises(
            ApprovalValidationError,
            match="No existe la tarea #999",
        ):
            service.approve(
                task_id=999,
                authorized_user_id=(
                    APPROVER_USER_ID
                ),
                authorization_message_id=(
                    "telegram:chat:202"
                ),
                channel="telegram",
            )


def test_rejects_plan_with_pending_decisions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan = create_task_and_plan(
            database=database,
            pending_decisions=(
                "Decidir el punto de oro",
            ),
        )

        with pytest.raises(
            ApprovalValidationError,
            match=(
                "El plan no esta pendiente "
                "de aprobacion"
            ),
        ):
            create_service(
                database
            ).approve(
                task_id=task.id,
                authorized_user_id=(
                    APPROVER_USER_ID
                ),
                authorization_message_id=(
                    "telegram:chat:203"
                ),
                channel="telegram",
            )

        stored_plan = TaskPlanRepository(
            database
        ).get_by_id(plan.id)

        assert stored_plan is not None
        assert (
            stored_plan.status
            == PlanStatus.PENDING_CLARIFICATION
        )


def test_repeated_approval_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        service = create_service(database)

        first = service.approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:204"
            ),
            channel="telegram",
        )

        second = service.approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:205"
            ),
            channel="telegram",
        )

        assert not first.already_approved
        assert second.already_approved
        assert (
            second.approval
            == first.approval
        )


def test_rejects_empty_approver_configuration() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        with pytest.raises(
            ValueError,
            match=(
                "approver_user_ids no puede"
            ),
        ):
            ApprovalService(
                task_repository=TaskRepository(
                    database
                ),
                plan_repository=(
                    TaskPlanRepository(
                        database
                    )
                ),
                approval_repository=(
                    TaskApprovalRepository(
                        database
                    )
                ),
                approver_user_ids=(),
            )

def test_cancels_approved_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        service = create_service(database)

        approved = service.approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:cancel-1"
            ),
            channel="telegram",
        )

        result = service.cancel(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
        )

        assert not result.already_cancelled
        assert (
            result.task.status
            == TaskStatus.CANCELLED
        )
        assert (
            result.plan.status
            == PlanStatus.APPROVED
        )
        assert (
            result.approval
            == approved.approval
        )
        assert (
            result.cancelled_user_id
            == APPROVER_USER_ID
        )


def test_rejects_cancellation_by_non_approver() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        service = create_service(database)

        service.approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:cancel-2"
            ),
            channel="telegram",
        )

        with pytest.raises(
            ApprovalPermissionError,
            match="No tienes permiso",
        ):
            service.cancel(
                task_id=task.id,
                authorized_user_id=(
                    "177448510"
                ),
            )

        stored = TaskRepository(
            database
        ).get_by_id(task.id)

        assert stored is not None
        assert (
            stored.status
            == TaskStatus.APPROVED
        )


def test_repeated_cancellation_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        service = create_service(database)

        service.approve(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
            authorization_message_id=(
                "telegram:chat:cancel-3"
            ),
            channel="telegram",
        )

        first = service.cancel(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
        )

        second = service.cancel(
            task_id=task.id,
            authorized_user_id=(
                APPROVER_USER_ID
            ),
        )

        assert not first.already_cancelled
        assert second.already_cancelled
        assert second.task == first.task
        assert (
            second.approval
            == first.approval
        )


def test_rejects_cancellation_without_approval() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_task_and_plan(
            database
        )

        with pytest.raises(
            ApprovalValidationError,
            match=(
                "no tiene una aprobacion"
            ),
        ):
            create_service(
                database
            ).cancel(
                task_id=task.id,
                authorized_user_id=(
                    APPROVER_USER_ID
                ),
            )