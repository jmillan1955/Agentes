from app.context import (
    ContextDatabase,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
    TaskRepository,
)
from app.models import (
    ChannelName,
    ContentType,
    IncomingMessage,
)
from app.orchestrator import Orchestrator
from app.planning import (
    PlanStatus,
    TaskPlan,
)
from app.planning.clarification_workflow import (
    ClarificationWorkflowResult,
)
from app.planning.service import (
    GeneratedPlan,
)
from app.tasks import (
    TaskClarificationResponse,
    TaskRecord,
    TaskStatus,
)


class FakeClarificationWorkflowService:
    def __init__(self) -> None:
        self.task_id: int | None = None
        self.session_id: int | None = None
        self.response_message_id: (
            str | None
        ) = None
        self.answer: str | None = None

    def respond(
        self,
        task_id: int,
        session_id: int,
        response_message_id: str,
        answer: str,
    ) -> ClarificationWorkflowResult:
        self.task_id = task_id
        self.session_id = session_id
        self.response_message_id = (
            response_message_id
        )
        self.answer = answer

        task = TaskRecord(
            id=task_id,
            project_id=1,
            session_id=session_id,
            source_message_id="mensaje-tarea",
            title="Crear puntuacion_padel",
            description=(
                "Crear una aplicación para "
                "controlar partidos de pádel"
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
            updated_at="2026-08-25T08:10:00Z",
            authorized_at=None,
            completed_at=None,
        )

        clarification = (
            TaskClarificationResponse(
                id=1,
                task_id=task_id,
                response_message_id=(
                    response_message_id
                ),
                questions=(
                    (
                        "¿Qué tipo de aplicación "
                        "necesitas?"
                    ),
                ),
                answer=answer,
                created_at=(
                    "2026-08-25T08:05:00Z"
                ),
            )
        )

        plan = TaskPlan(
            id=1,
            task_id=task_id,
            version=1,
            status=(
                PlanStatus
                .PENDING_CLARIFICATION
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
            ),
            excluded_items=(
                "No ejecutar sin autorización",
            ),
            completion_criteria=(
                "Registrar un partido",
                "Calcular el resultado",
            ),
            created_at="2026-08-25T08:08:00Z",
            updated_at="2026-08-25T08:08:00Z",
        )

        return ClarificationWorkflowResult(
            task=task,
            clarification=clarification,
            generated_plan=GeneratedPlan(
                plan=plan,
                model="modelo-prueba",
                elapsed_seconds=2.5,
            ),
        )


def create_orchestrator(
    database: ContextDatabase,
    workflow: (
        FakeClarificationWorkflowService
        | None
    ),
) -> Orchestrator:
    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    return Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=MessageRepository(
            database
        ),
        task_repository=TaskRepository(
            database
        ),
        context_query_service=None,
        context_builder=None,
        response_generation_service=None,
        clarification_workflow_service=(
            workflow
        ),
    )


def create_command(
    text: str,
) -> IncomingMessage:
    return IncomingMessage(
        channel=ChannelName.TELEGRAM,
        user_id="usuario",
        conversation_id="conversacion",
        content_type=ContentType.COMMAND,
        text=text,
        message_id="telegram:123:50",
    )


def test_processes_respond_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        workflow = (
            FakeClarificationWorkflowService()
        )

        orchestrator = create_orchestrator(
            database=database,
            workflow=workflow,
        )

        outgoing = orchestrator.process(
            create_command(
                (
                    "/responder 2 Será una "
                    "aplicación web para móvil."
                )
            )
        )

        assert outgoing.text is not None
        assert (
            "PLAN PROPUESTO — VERSIÓN 1"
            in outgoing.text
        )
        assert (
            "Proyecto: puntuacion_padel"
            in outgoing.text
        )
        assert "Angular" in outgoing.text
        assert (
            "DECISIONES PENDIENTES"
            in outgoing.text
        )
        assert (
            "/responder 2 <tus aclaraciones>"
            in outgoing.text
        )

        assert workflow.task_id == 2
        assert workflow.session_id == 1
        assert (
            workflow.response_message_id
            == "telegram:123:50"
        )
        assert (
            workflow.answer
            == (
                "Será una aplicación "
                "web para móvil."
            )
        )

        assert (
            outgoing.metadata["route"]
            == "clarification_workflow"
        )
        assert (
            outgoing.metadata["plan_version"]
            == 1
        )
        assert (
            outgoing.metadata["model"]
            == "modelo-prueba"
        )
        assert (
            outgoing.metadata[
                "elapsed_seconds"
            ]
            == 2.5
        )


def test_requires_task_and_answer() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            workflow=(
                FakeClarificationWorkflowService()
            ),
        )

        outgoing = orchestrator.process(
            create_command("/responder")
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar la tarea "
            "y la respuesta"
            in outgoing.text
        )


def test_rejects_invalid_task_identifier() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            workflow=(
                FakeClarificationWorkflowService()
            ),
        )

        outgoing = orchestrator.process(
            create_command(
                "/responder abc Respuesta"
            )
        )

        assert outgoing.text is not None
        assert (
            "debe ser un número entero"
            in outgoing.text
        )