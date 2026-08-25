from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskClarificationResponseRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.planning.clarification_workflow import (
    ClarificationWorkflowService,
)
from app.planning.service import (
    GeneratedPlan,
)
from app.tasks import TaskStatus


class FakePlanningService:
    def __init__(
        self,
        plan_repository: TaskPlanRepository,
        pending_decisions: tuple[
            str,
            ...,
        ],
    ) -> None:
        self._plan_repository = (
            plan_repository
        )
        self._pending_decisions = (
            pending_decisions
        )

    def generate(
        self,
        task_id: int,
    ) -> GeneratedPlan:
        plan = self._plan_repository.create(
            task_id=task_id,
            objective=(
                "Crear una aplicación para "
                "controlar partidos de pádel"
            ),
            scope=(
                "Definir equipos y jugadores",
                "Controlar la puntuación",
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
                self._pending_decisions
            ),
            excluded_items=(
                "No ejecutar sin autorización",
            ),
            completion_criteria=(
                "Registrar un partido",
                "Calcular el resultado",
            ),
        )

        return GeneratedPlan(
            plan=plan,
            model="modelo-prueba",
            elapsed_seconds=1.5,
        )


def create_pending_task(
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

    task_repository = TaskRepository(
        database
    )

    task = task_repository.create(
        project_id=project.id,
        session_id=session.id,
        source_message_id="mensaje-tarea",
        title="Crear puntuacion_padel",
        description=(
            "Crear una aplicación para llevar "
            "el marcador de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )

    task = (
        task_repository
        .set_missing_information(
            task_id=task.id,
            missing_information=(
                (
                    "¿Qué tipo de aplicación "
                    "necesitas?"
                ),
            ),
        )
    )

    return task, session


def create_workflow(
    database: ContextDatabase,
    pending_decisions: tuple[str, ...],
) -> ClarificationWorkflowService:
    plan_repository = TaskPlanRepository(
        database
    )

    return ClarificationWorkflowService(
        task_repository=TaskRepository(
            database
        ),
        clarification_repository=(
            TaskClarificationResponseRepository(
                database
            )
        ),
        planning_service=FakePlanningService(
            plan_repository=plan_repository,
            pending_decisions=(
                pending_decisions
            ),
        ),
    )


def test_generates_plan_and_new_questions() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, session = create_pending_task(
            database
        )

        workflow = create_workflow(
            database=database,
            pending_decisions=(
                "¿Se utilizará punto de oro?",
                "¿Cuántos sets tendrá el partido?",
            ),
        )

        result = workflow.respond(
            task_id=task.id,
            session_id=session.id,
            response_message_id=(
                "telegram:123:30"
            ),
            answer=(
                "Será una aplicación web "
                "adaptada al móvil."
            ),
        )

        assert (
            result.task.status
            == TaskStatus.PENDING_CLARIFICATION
        )

        assert result.task.missing_information == (
            "¿Se utilizará punto de oro?",
            "¿Cuántos sets tendrá el partido?",
        )

        assert (
            result.generated_plan.plan.version
            == 1
        )

        assert (
            result.generated_plan.plan
            .technologies
            == (
                "Angular",
                "FastAPI",
                "SQLite",
            )
        )

        responses = (
            TaskClarificationResponseRepository(
                database
            ).list_by_task(task.id)
        )

        assert len(responses) == 1
        assert (
            "aplicación web"
            in responses[0].answer
        )


def test_moves_task_to_pending_approval() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, session = create_pending_task(
            database
        )

        workflow = create_workflow(
            database=database,
            pending_decisions=(),
        )

        result = workflow.respond(
            task_id=task.id,
            session_id=session.id,
            response_message_id=(
                "telegram:123:31"
            ),
            answer=(
                "Utilizar punto de oro "
                "y partidos al mejor de tres sets."
            ),
        )

        assert (
            result.task.status
            == TaskStatus.PENDING_APPROVAL
        )

        assert (
            result.task.missing_information
            == ()
        )

        assert result.task.plan == (
            "Crear motor de puntuación",
            "Crear API",
            "Crear interfaz web",
        )


def test_rejects_task_from_other_session() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, _ = create_pending_task(
            database
        )

        workflow = create_workflow(
            database=database,
            pending_decisions=(),
        )

        try:
            workflow.respond(
                task_id=task.id,
                session_id=999,
                response_message_id="mensaje",
                answer="Respuesta",
            )

            assert False

        except ValueError as error:
            assert (
                "no pertenece a esta conversación"
                in str(error)
            )