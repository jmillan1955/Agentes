import json

import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskClarificationResponseRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.planning import (
    PlanStatus,
    PlanningPromptBuilder,
)
from app.planning.service import (
    PlanningGenerationError,
    PlanningService,
)
from app.providers import LanguageResponse


PLAN_DATA = {
    "objective": (
        "Crear una aplicación web para "
        "controlar partidos de pádel"
    ),
    "scope": [
        "Definir equipos y jugadores",
        "Registrar puntos",
        "Controlar juegos, sets y partidos",
    ],
    "technologies": [
        "Angular",
        "FastAPI",
        "SQLite",
    ],
    "interfaces": [
        "Interfaz web adaptable a móvil",
        "API REST",
    ],
    "inputs": [
        "Añadir punto",
        "Corregir punto",
    ],
    "outputs": [
        "Marcador visual",
        "Aviso de fin de juego",
        "Aviso de fin de set",
        "Aviso de fin de partido",
    ],
    "data_entities": [
        "Partido",
        "Equipo",
        "Jugador",
        "Set",
        "Juego",
    ],
    "business_rules": [
        "Puntuación reglamentaria de pádel",
    ],
    "phases": [
        "Crear motor de puntuación",
        "Crear API",
        "Crear interfaz web",
    ],
    "tests": [
        "Probar puntos, juegos y sets",
    ],
    "deployment": [
        "Ejecución local inicial",
    ],
    "pending_decisions": [
        "Confirmar si se utiliza punto de oro",
    ],
    "excluded_items": [
        "No ejecutar cambios sin autorización",
    ],
    "completion_criteria": [
        "Registrar equipos y jugadores",
        "Calcular el resultado del partido",
    ],
}


class FakeLanguageProvider:
    def __init__(
        self,
        text: str,
    ) -> None:
        self._text = text
        self.received_prompt: str | None = None
        self.received_system_prompt: (
            str | None
        ) = None

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LanguageResponse:
        self.received_prompt = prompt
        self.received_system_prompt = (
            system_prompt
        )

        return LanguageResponse(
            text=self._text,
            model="modelo-prueba",
            elapsed_seconds=1.25,
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
        source_message_id="mensaje-tarea",
        title="Crea el proyecto puntuacion_padel",
        description=(
            "Crear una aplicación para llevar "
            "el marcador de partidos de pádel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )

    return repository.set_missing_information(
        task_id=task.id,
        missing_information=(
            "¿Qué tipo de aplicación necesitas?",
        ),
    )


def create_service(
    database: ContextDatabase,
    response_text: str,
) -> tuple[
    PlanningService,
    FakeLanguageProvider,
]:
    provider = FakeLanguageProvider(
        response_text
    )

    service = PlanningService(
        task_repository=TaskRepository(
            database
        ),
        clarification_repository=(
            TaskClarificationResponseRepository(
                database
            )
        ),
        plan_repository=TaskPlanRepository(
            database
        ),
        prompt_builder=PlanningPromptBuilder(),
        language_provider=provider,
    )

    return service, provider


def test_generates_and_persists_plan() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        clarification_repository = (
            TaskClarificationResponseRepository(
                database
            )
        )

        clarification_repository.create(
            task_id=task.id,
            response_message_id="mensaje-respuesta",
            questions=task.missing_information,
            answer=(
                "Será una aplicación web "
                "adaptada al móvil."
            ),
        )

        service, provider = create_service(
            database=database,
            response_text=json.dumps(
                PLAN_DATA,
                ensure_ascii=False,
            ),
        )

        generated = service.generate(
            task.id
        )

        assert generated.plan.version == 1
        assert (
            generated.plan.status
            == PlanStatus.PENDING_CLARIFICATION
        )
        assert generated.model == "modelo-prueba"
        assert generated.elapsed_seconds == 1.25
        assert (
            "aplicación web adaptada al móvil"
            in (
                provider.received_prompt
                or ""
            )
        )

        stored = TaskPlanRepository(
            database
        ).get_latest(task.id)

        assert stored == generated.plan


def test_accepts_json_inside_code_fence() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        response_text = (
            "```json\n"
            + json.dumps(
                PLAN_DATA,
                ensure_ascii=False,
            )
            + "\n```"
        )

        service, _ = create_service(
            database=database,
            response_text=response_text,
        )

        generated = service.generate(
            task.id
        )

        assert generated.plan.version == 1


def test_rejects_invalid_json() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        service, _ = create_service(
            database=database,
            response_text=(
                "Esta respuesta no es JSON"
            ),
        )

        with pytest.raises(
            PlanningGenerationError,
            match="no contiene un objeto JSON",
        ):
            service.generate(task.id)


def test_rejects_missing_list_field() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task = create_task(database)

        incomplete = dict(PLAN_DATA)
        incomplete.pop("interfaces")

        service, _ = create_service(
            database=database,
            response_text=json.dumps(
                incomplete,
                ensure_ascii=False,
            ),
        )

        with pytest.raises(
            PlanningGenerationError,
            match=(
                "El campo 'interfaces' "
                "debe ser una lista JSON"
            ),
        ):
            service.generate(task.id)


def test_rejects_unknown_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        service, _ = create_service(
            database=database,
            response_text=json.dumps(
                PLAN_DATA,
                ensure_ascii=False,
            ),
        )

        with pytest.raises(
            ValueError,
            match="No existe la tarea",
        ):
            service.generate(999)