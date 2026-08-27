from hashlib import sha256
from pathlib import Path

from types import SimpleNamespace
from unittest.mock import Mock

from app.context import (
    ContextBuilder,
    ContextDatabase,
    ContextQueryService,
    ContextSearchService,
    DocumentRepository,
    MessageRepository,
    ProjectRepository,
    SessionRepository,
    TaskPlanRepository,
    TaskRepository,
    TaskApprovalRepository,
    TaskExecutionRepository,
)
from app.execution.factory import (
    create_execution_runtime,
)
from app.approvals.formatter import (
    ApprovalFormatter,
)
from app.approvals.service import (
    ApprovalService,
)
from app.models import (
    Attachment,
    ChannelName,
    ContentType,
    IncomingMessage,
)
from app.orchestrator import Orchestrator
from app.providers import (
    LanguageProviderError,
)
from app.response_generation_service import (
    GeneratedAnswer,
)
from app.tasks import TaskStatus
from app.execution.service import (
    ExecutionPreparationError,
)
class FakeResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
        include_context: bool = True,
        response_style: str | None = None,
    ) -> GeneratedAnswer:
        return GeneratedAnswer(
            text=(
                "Respuesta generada para: "
                f"{query}"
            ),
            model="modelo-de-prueba",
            elapsed_seconds=1.5,
            document_paths=(),
            message_ids=(),
            context_characters=100,
            context_truncated=False,
        )


class FailingResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
        include_context: bool = True,
        response_style: str | None = None,
    ) -> GeneratedAnswer:
        raise LanguageProviderError(
            "Proveedor no disponible"
        )


class UnexpectedResponseGenerationService:
    def generate(
        self,
        project_id: int,
        query: str,
        current_message_id: str,
        include_context: bool = True,
        response_style: str | None = None,
    ):
        raise AssertionError(
            "Una tarea no debe enviarse "
            "al proveedor de lenguaje"
        )

def create_orchestrator(
    database: ContextDatabase,
    context_query_service: (
        ContextQueryService | None
    ) = None,
    response_generation_service=None,
    execution_preparation_service=None,
    execution_runner=None,
) -> Orchestrator:
    if context_query_service is None:
        context_query_service = (
            ContextQueryService(database)
        )

    if response_generation_service is None:
        response_generation_service = (
            FakeResponseGenerationService()
        )

    project = ProjectRepository(
        database
    ).save(
        name="Agente Orquestador",
        root_path="ruta-del-proyecto",
    )

    document_repository = DocumentRepository(
        database
    )
    message_repository = MessageRepository(
        database
    )

    context_builder = ContextBuilder(
        ContextSearchService(
            document_repository=(
                document_repository
            ),
            message_repository=(
                message_repository
            ),
        )
    )

    return Orchestrator(
        project_id=project.id,
        session_repository=SessionRepository(
            database
        ),
        message_repository=message_repository,
        task_repository=TaskRepository(
            database
        ),
        context_query_service=(
            context_query_service
        ),
        context_builder=context_builder,
        response_generation_service=(
            response_generation_service
        ),
        task_plan_repository=(
            TaskPlanRepository(database)
        ),
        approval_service=ApprovalService(
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
            execution_repository=(
                TaskExecutionRepository(
                    database
                )
            ),
            approver_user_ids=(123456,),
        ),
        approval_formatter=(
            ApprovalFormatter()
        ),
        execution_preparation_service=(
            execution_preparation_service
        ),
        execution_runner=execution_runner,
    )

def test_processes_text_message() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Hola, agente.",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.channel == incoming.channel
        assert (
            outgoing.conversation_id
            == incoming.conversation_id
        )
        assert (
            outgoing.correlation_id
            == incoming.message_id
        )
        assert outgoing.text is not None
        assert "Hola, agente." in outgoing.text
        assert (
            outgoing.metadata["model"]
            == "modelo-de-prueba"
        )
        assert (
            outgoing.metadata[
                "elapsed_seconds"
            ]
            == 1.5
        )


def test_persists_input_and_output() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Mensaje persistente.",
        )

        outgoing = orchestrator.process(
            incoming
        )

        session = SessionRepository(
            database
        ).list_active()[0]

        messages = MessageRepository(
            database
        ).list_by_session(
            session.id
        )

        assert len(messages) == 2
        assert messages[0].direction == "incoming"
        assert (
            messages[0].text
            == "Mensaje persistente."
        )
        assert messages[1].direction == "outgoing"
        assert (
            messages[1].correlation_id
            == incoming.message_id
        )
        assert messages[1].text == outgoing.text


def test_reuses_session_for_same_conversation() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        first = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Primer mensaje.",
        )

        second = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text="Segundo mensaje.",
        )

        orchestrator.process(first)
        orchestrator.process(second)

        sessions = SessionRepository(
            database
        ).list_active()

        assert len(sessions) == 1

        messages = MessageRepository(
            database
        ).list_by_session(
            sessions[0].id
        )

        assert len(messages) == 4


def test_reports_unsupported_content_type() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        attachment = Attachment(
            attachment_id="documento-1",
            content_type=ContentType.DOCUMENT,
            filename="prueba.txt",
            mime_type="text/plain",
            size_bytes=100,
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.DOCUMENT,
            attachments=(attachment,),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert "document" in outgoing.text
        assert (
            "solamente proceso texto"
            in outgoing.text
        )


def test_returns_context_for_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/contexto",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Contexto del Agente Orquestador"
            in outgoing.text
        )
        assert (
            "Proyecto: Agente Orquestador"
            in outgoing.text
        )
        assert "Sesiones:" in outgoing.text
        assert (
            "Mensajes registrados:"
            in outgoing.text
        )


def test_searches_context_for_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        project = ProjectRepository(
            database
        ).save(
            name="Proyecto documental",
            root_path="ruta-documental",
        )

        content = (
            "Telegram es el canal de entrada "
            "del Agente Orquestador."
        )

        document_repository = (
            DocumentRepository(database)
        )

        document_repository.save(
            project_id=project.id,
            relative_path="docs/telegram.md",
            title="Integración Telegram",
            content=content,
            content_hash=sha256(
                content.encode("utf-8")
            ).hexdigest(),
        )

        message_repository = (
            MessageRepository(database)
        )

        context_builder = ContextBuilder(
            ContextSearchService(
                document_repository=(
                    document_repository
                ),
                message_repository=(
                    message_repository
                ),
            )
        )

        orchestrator = Orchestrator(
            project_id=project.id,
            session_repository=(
                SessionRepository(database)
            ),
            message_repository=(
                message_repository
            ),
            task_repository=TaskRepository(
                database
            ),
            context_query_service=(
                ContextQueryService(database)
            ),
            context_builder=context_builder,
            response_generation_service=(
                FakeResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/buscar Telegram",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "CONTEXTO RECUPERADO"
            in outgoing.text
        )
        assert (
            "Integración Telegram"
            in outgoing.text
        )


def test_requires_search_query() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/buscar",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar qué quieres buscar"
            in outgoing.text
        )


def test_controls_language_provider_error() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            response_generation_service=(
                FailingResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "¿Cuál es la capital "
                "de Portugal?"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "No se ha podido generar "
            "la respuesta"
            in outgoing.text
        )
        assert (
            "Proveedor no disponible"
            in outgoing.text
        )
        assert (
            outgoing.metadata["error"]
            == "LanguageProviderError"
        )
        assert (
            incoming.message_id
            not in outgoing.text
        )

def test_adds_routing_decision_to_metadata() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "Añade un canal de correo "
                "al Agente Orquestador"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert (
            outgoing.metadata["routing_kind"]
            == "task"
        )
        assert (
            outgoing.metadata[
                "routing_confidence"
            ]
            == 0.90
        )
        assert (
            outgoing.metadata[
                "routing_project"
            ]
            == "Agente Orquestador"
        )
        assert not outgoing.metadata[
            "routing_requires_clarification"
        ]

def test_classifies_request_from_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text=(
                "/clasificar Añade un canal "
                "de correo"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "CLASIFICACIÓN DE LA PETICIÓN"
            in outgoing.text
        )
        assert "Tipo: task" in outgoing.text
        assert "Confianza: 90%" in outgoing.text
        assert (
            "Necesita aclaración: No"
            in outgoing.text
        )

def test_requires_request_to_classify() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/clasificar",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar una petición"
            in outgoing.text
        )

def test_routes_task_without_calling_language_provider() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database=database,
            response_generation_service=(
                UnexpectedResponseGenerationService()
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "Crea el proyecto "
                "agente_audioText"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "PETICIÓN IDENTIFICADA COMO TAREA"
            in outgoing.text
        )
        assert (
            "No se ha ejecutado ningún cambio"
            in outgoing.text
        )
        assert (
            outgoing.metadata["routing_kind"]
            == "task"
        )
        assert (
            outgoing.metadata["route"]
            == "task_handler"
        )
        assert (
            outgoing.metadata["task_status"]
            == "pending_clarification"
        )
        assert len(
            outgoing.metadata[
                "task_missing_information"
            ]
        ) == 5
        assert (
            "Necesito que aclares"
            in (outgoing.text or "")
        )
        assert "model" not in outgoing.metadata

def test_persists_routed_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.TEXT,
            text=(
                "Crea el proyecto "
                "agente_audioText"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        task_id = outgoing.metadata[
            "task_id"
        ]

        task = TaskRepository(
            database
        ).get_by_id(task_id)

        assert task is not None
        assert (
            task.source_message_id
            == incoming.message_id
        )
        assert (
            task.target_project_name
            == "agente_audioText"
        )
        assert (
            task.status
            == TaskStatus.PENDING_CLARIFICATION
        )
        assert len(
            task.missing_information
        ) == 5
        assert (
            "Necesito que aclares"
            in (outgoing.text or "")
        )
        assert (
            f"Identificador: #{task.id}"
            in (outgoing.text or "")
        )

def test_approves_task_plan_with_command(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_runtime = (
            create_execution_runtime(
                database=database,
                execution_workspace_root=(
                    tmp_path / "executions"
                ),
                protected_project_root=(
                    tmp_path / "orchestrator"
                ),
                sandbox_gateway_url=None,
                sandbox_gateway_token=None,
                sandbox_gateway_timeout_seconds=(
                    150
                ),
            )
        )

        orchestrator = create_orchestrator(
            database=database,
            execution_preparation_service=(
                execution_runtime
                .preparation_service
            ),
            execution_runner=(
                execution_runtime.runner
            ),
        )
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
            conversation_id="chat-123456",
        )

        task_repository = TaskRepository(
            database
        )

        task = task_repository.create(
            project_id=project.id,
            session_id=session.id,
            source_message_id=(
                "mensaje-tarea-aprobable"
            ),
            title="Crear puntuacion_padel",
            description=(
                "Crear una aplicacion web "
                "para controlar el marcador"
            ),
            target_project_name=(
                "puntuacion_padel"
            ),
        )

        plan = TaskPlanRepository(
            database
        ).create(
            task_id=task.id,
            objective=(
                "Crear una aplicacion web "
                "para controlar partidos "
                "de padel"
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
            ),
            inputs=(
                "Anadir punto",
                "Corregir punto",
            ),
            outputs=(
                "Marcador actualizado",
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
                "Crear motor de puntuacion",
                "Crear API",
                "Crear interfaz web",
            ),
            tests=(
                "Probar juegos y sets",
            ),
            deployment=(
                "Ejecucion local inicial",
            ),
            excluded_items=(
                "No ejecutar sin autorizacion",
            ),
            completion_criteria=(
                "Registrar un partido",
                "Calcular el resultado",
            ),
        )

        task_repository.set_plan(
            task_id=task.id,
            plan=plan.phases,
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text=f"/aprobar {task.id}",
            message_id=(
                "telegram:chat-123456:300"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert outgoing.text.startswith(
            "PLAN APROBADO"
        )
        assert (
            f"Tarea: #{task.id}"
            in outgoing.text
        )
        assert (
            "Proyecto: puntuacion_padel"
            in outgoing.text
        )
        assert (
            "No se ha creado ni modificado "
            "codigo del proyecto."
            in outgoing.text
        )

        assert (
            outgoing.metadata["route"]
            == "approval_service"
        )
        assert (
            outgoing.metadata["task_id"]
            == task.id
        )
        assert (
            outgoing.metadata["plan_id"]
            == plan.id
        )
        assert (
            outgoing.metadata["plan_version"]
            == plan.version
        )
        assert (
            outgoing.metadata[
                "already_approved"
            ]
            is False
        )

        stored_task = task_repository.get_by_id(
            task.id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.APPROVED
        )
        assert (
            stored_task.status
            == TaskStatus.APPROVED
        )
        preparation_response = (
            orchestrator.process(
                IncomingMessage(
                    channel=(
                        ChannelName.TELEGRAM
                    ),
                    user_id="123456",
                    conversation_id=(
                        "chat-123456"
                    ),
                    content_type=(
                        ContentType.COMMAND
                    ),
                    text=(
                        "/preparar_ejecucion "
                        f"{task.id}"
                    ),
                    message_id=(
                        "telegram:"
                        "chat-123456:3001"
                    ),
                )
            )
        )

        assert (
            preparation_response.text
            is not None
        )
        assert (
            preparation_response.text
            .startswith(
                "EJECUCION PREPARADA"
            )
        )
        assert (
            "No se ha ejecutado codigo."
            in preparation_response.text
        )

        execution_repository = (
            TaskExecutionRepository(
                database
            )
        )

        stored_execution = (
            execution_repository
            .get_by_task_id(task.id)
        )

        assert stored_execution is not None
        assert (
            stored_execution.status.value
            == "prepared"
        )
        assert (
            not Path(
                stored_execution
                .workspace_path
            ).exists()
        )
        cancellation = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text=f"/cancelar {task.id}",
            message_id=(
                "telegram:chat-123456:301"
            ),
        )

        cancellation_response = (
            orchestrator.process(
                cancellation
            )
        )

        assert (
            cancellation_response.text
            is not None
        )
        cancelled_execution = (
            execution_repository
            .get_by_task_id(task.id)
        )

        assert cancelled_execution is not None
        assert (
            cancelled_execution.status.value
            == "cancelled"
        )
        assert (
            cancelled_execution.finished_at
            is not None
        )
        assert (
            cancellation_response.text
            .startswith(
                "TAREA APROBADA CANCELADA"
            )
        )
        assert (
            f"Tarea: #{task.id}"
            in cancellation_response.text
        )
        assert (
            "Plan aprobado conservado: "
            f"version {plan.version}"
            in cancellation_response.text
        )
        assert (
            "La autorizacion se conserva "
            "como historial."
            in cancellation_response.text
        )
        assert (
            "La tarea no podra iniciar "
            "su ejecucion."
            in cancellation_response.text
        )

        assert (
            cancellation_response.metadata[
                "route"
            ]
            == "cancellation_service"
        )
        assert (
            cancellation_response.metadata[
                "task_id"
            ]
            == task.id
        )
        assert (
            cancellation_response.metadata[
                "task_status"
            ]
            == TaskStatus.CANCELLED.value
        )
        assert (
            cancellation_response.metadata[
                "plan_id"
            ]
            == plan.id
        )
        assert (
            cancellation_response.metadata[
                "plan_status"
            ]
            == "approved"
        )
        assert (
            cancellation_response.metadata[
                "already_cancelled"
            ]
            is False
        )

        cancelled_task = (
            task_repository.get_by_id(
                task.id
            )
        )

        assert cancelled_task is not None
        assert (
            cancelled_task.status
            == TaskStatus.CANCELLED
        )

        stored_plan = (
            TaskPlanRepository(database)
            .get_by_id(plan.id)
        )

        assert stored_plan is not None
        assert (
            stored_plan.status.value
            == "approved"
        )
        repeated_response = (
            orchestrator.process(
                IncomingMessage(
                    channel=(
                        ChannelName.TELEGRAM
                    ),
                    user_id="123456",
                    conversation_id=(
                        "chat-123456"
                    ),
                    content_type=(
                        ContentType.COMMAND
                    ),
                    text=(
                        f"/cancelar {task.id}"
                    ),
                    message_id=(
                        "telegram:"
                        "chat-123456:302"
                    ),
                )
            )
        )

        assert (
            repeated_response.text
            is not None
        )
        assert (
            repeated_response.text.startswith(
                "TAREA YA CANCELADA"
            )
        )
        assert (
            repeated_response.metadata[
                "already_cancelled"
            ]
            is True
        )
        assert (
            repeated_response.metadata[
                "task_status"
            ]
            == TaskStatus.CANCELLED.value
        )

def test_approve_command_requires_task_id() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/aprobar",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar la tarea"
            in outgoing.text
        )
        assert (
            outgoing.metadata[
                "approval_error"
            ]
            == "missing_task_id"
        )


def test_approve_command_rejects_invalid_id() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/aprobar tarea",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "debe ser un numero entero"
            in outgoing.text
        )
        assert (
            outgoing.metadata[
                "approval_error"
            ]
            == "invalid_task_id"
        )


def test_approve_command_rejects_non_approver() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="177448510",
            conversation_id="chat-177448510",
            content_type=ContentType.COMMAND,
            text="/aprobar 999",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "No tienes permiso"
            in outgoing.text
        )
        assert (
            outgoing.metadata[
                "approval_error"
            ]
            == "ApprovalPermissionError"
        )

def test_shows_latest_task_plan() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

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
            conversation_id="chat-123456",
        )

        task = TaskRepository(
            database
        ).create(
            project_id=project.id,
            session_id=session.id,
            source_message_id=(
                "mensaje-ver-plan"
            ),
            title="Crear proyecto",
            description="Crear proyecto",
            target_project_name=(
                "proyecto_prueba"
            ),
        )

        plan = TaskPlanRepository(
            database
        ).create(
            task_id=task.id,
            objective=(
                "Crear el proyecto de prueba"
            ),
            scope=(
                "Construir la primera version",
            ),
            technologies=(
                "FastAPI",
                "SQLite",
            ),
            phases=(
                "Definir arquitectura",
                "Implementar la aplicacion",
            ),
            completion_criteria=(
                "Superar todas las pruebas",
            ),
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text=f"/ver_plan {task.id}",
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "PLAN PROPUESTO"
            in outgoing.text
        )
        assert (
            f"Tarea: #{task.id}"
            in outgoing.text
        )
        assert (
            "Proyecto: proyecto_prueba"
            in outgoing.text
        )
        assert (
            "Crear el proyecto de prueba"
            in outgoing.text
        )
        assert (
            outgoing.metadata["route"]
            == "plan_query"
        )
        assert (
            outgoing.metadata["task_id"]
            == task.id
        )
        assert (
            outgoing.metadata["plan_id"]
            == plan.id
        )
        assert (
            outgoing.metadata["plan_version"]
            == plan.version
        )

def test_cancel_command_requires_task_id() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        orchestrator = create_orchestrator(
            database
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/cancelar",
            message_id=(
                "telegram:chat-123456:400"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar la tarea que "
            "quieres cancelar."
            in outgoing.text
        )
        assert (
            outgoing.metadata["route"]
            == "cancellation_service"
        )
        assert (
            outgoing.metadata[
                "cancellation_error"
            ]
            == "missing_task_id"
        )

def test_prepare_execution_with_command() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        preparation_service = Mock()
        execution_runner = Mock()

        preparation_service.prepare.return_value = (
            SimpleNamespace(
                execution=SimpleNamespace(
                    id=5,
                    task_id=4,
                    plan_id=8,
                    approval_id=2,
                    status=SimpleNamespace(
                        value="prepared"
                    ),
                    workspace_path=(
                        "ruta/proyecto_temporal"
                    ),
                ),
                already_prepared=False,
            )
        )

        orchestrator = create_orchestrator(
            database=database,
            execution_preparation_service=(
                preparation_service
            ),
            execution_runner=execution_runner,
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/preparar_ejecucion 4",
            message_id=(
                "telegram:chat-123456:500"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert outgoing.text.startswith(
            "EJECUCION PREPARADA"
        )
        assert "Ejecucion: #5" in outgoing.text
        assert "Tarea: #4" in outgoing.text
        assert "Plan: #8" in outgoing.text
        assert (
            "Estado: prepared"
            in outgoing.text
        )
        assert (
            "No se ha ejecutado codigo."
            in outgoing.text
        )

        assert (
            outgoing.metadata["route"]
            == "execution_preparation_service"
        )
        assert (
            outgoing.metadata["execution_id"]
            == 5
        )
        assert (
            outgoing.metadata["task_id"]
            == 4
        )
        assert (
            outgoing.metadata[
                "already_prepared"
            ]
            is False
        )

        preparation_service.prepare.assert_called_once_with(
            task_id=4,
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:chat-123456:500"
            ),
            channel="telegram",
        )

        execution_runner.run.assert_not_called()


def test_prepare_execution_requires_task_id() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        preparation_service = Mock()
        execution_runner = Mock()

        orchestrator = create_orchestrator(
            database=database,
            execution_preparation_service=(
                preparation_service
            ),
            execution_runner=execution_runner,
        )

        incoming = IncomingMessage(
            channel=ChannelName.TELEGRAM,
            user_id="123456",
            conversation_id="chat-123456",
            content_type=ContentType.COMMAND,
            text="/preparar_ejecucion",
            message_id=(
                "telegram:chat-123456:501"
            ),
        )

        outgoing = orchestrator.process(
            incoming
        )

        assert outgoing.text is not None
        assert (
            "Debes indicar la tarea cuya "
            "ejecucion quieres preparar."
            in outgoing.text
        )
        assert (
            outgoing.metadata["route"]
            == "execution_preparation_service"
        )
        assert (
            outgoing.metadata[
                "execution_error"
            ]
            == "missing_task_id"
        )

        preparation_service.prepare.assert_not_called()
        execution_runner.run.assert_not_called()

def test_prepare_execution_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        preparation_service = Mock()
        execution_runner = Mock()

        preparation_service.prepare.return_value = (
            SimpleNamespace(
                execution=SimpleNamespace(
                    id=5,
                    task_id=4,
                    plan_id=8,
                    approval_id=2,
                    status=SimpleNamespace(
                        value="prepared"
                    ),
                    workspace_path=(
                        "ruta/proyecto_temporal"
                    ),
                ),
                already_prepared=True,
            )
        )

        orchestrator = create_orchestrator(
            database=database,
            execution_preparation_service=(
                preparation_service
            ),
            execution_runner=execution_runner,
        )

        outgoing = orchestrator.process(
            IncomingMessage(
                channel=ChannelName.TELEGRAM,
                user_id="123456",
                conversation_id=(
                    "chat-123456"
                ),
                content_type=(
                    ContentType.COMMAND
                ),
                text=(
                    "/preparar_ejecucion 4"
                ),
                message_id=(
                    "telegram:"
                    "chat-123456:502"
                ),
            )
        )

        assert outgoing.text is not None
        assert outgoing.text.startswith(
            "EJECUCION YA PREPARADA"
        )
        assert (
            outgoing.metadata[
                "already_prepared"
            ]
            is True
        )

        execution_runner.run.assert_not_called()


def test_prepare_execution_reports_service_error() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        preparation_service = Mock()
        execution_runner = Mock()

        preparation_service.prepare.side_effect = (
            ExecutionPreparationError(
                "La tarea no tiene una "
                "autorizacion aprobada"
            )
        )

        orchestrator = create_orchestrator(
            database=database,
            execution_preparation_service=(
                preparation_service
            ),
            execution_runner=execution_runner,
        )

        outgoing = orchestrator.process(
            IncomingMessage(
                channel=ChannelName.TELEGRAM,
                user_id="123456",
                conversation_id=(
                    "chat-123456"
                ),
                content_type=(
                    ContentType.COMMAND
                ),
                text=(
                    "/preparar_ejecucion 4"
                ),
                message_id=(
                    "telegram:"
                    "chat-123456:503"
                ),
            )
        )

        assert outgoing.text == (
            "La tarea no tiene una "
            "autorizacion aprobada"
        )
        assert (
            outgoing.metadata["route"]
            == "execution_preparation_service"
        )
        assert (
            outgoing.metadata[
                "execution_error"
            ]
            == "ExecutionPreparationError"
        )
        assert (
            outgoing.metadata["task_id"]
            == 4
        )

        execution_runner.run.assert_not_called()