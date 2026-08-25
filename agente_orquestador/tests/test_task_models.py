import pytest

from app.tasks import (
    TaskRecord,
    TaskStatus,
)


def create_task(
    status: TaskStatus = (
        TaskStatus.PENDING_PLANNING
    ),
    missing_information: tuple[
        str,
        ...,
    ] = (),
    plan: tuple[str, ...] = (),
) -> TaskRecord:
    return TaskRecord(
        id=1,
        project_id=1,
        session_id=1,
        source_message_id="telegram:123:1",
        title="Crear agente_audioText",
        description=(
            "Crear un proyecto para convertir "
            "texto en audio"
        ),
        target_project_name=(
            "agente_audioText"
        ),
        status=status,
        missing_information=(
            missing_information
        ),
        plan=plan,
        created_at=(
            "2026-08-25T07:00:00.000Z"
        ),
        updated_at=(
            "2026-08-25T07:00:00.000Z"
        ),
        authorized_at=None,
        completed_at=None,
    )


def test_creates_pending_task() -> None:
    task = create_task()

    assert task.id == 1
    assert (
        task.status
        == TaskStatus.PENDING_PLANNING
    )
    assert (
        task.target_project_name
        == "agente_audioText"
    )
    assert not task.requires_clarification
    assert not task.requires_approval
    assert not task.is_terminal


def test_detects_required_clarification() -> None:
    task = create_task(
        status=(
            TaskStatus.PENDING_CLARIFICATION
        ),
        missing_information=(
            "Formato de entrada",
            "Formato de salida",
        ),
    )

    assert task.requires_clarification
    assert task.missing_information == (
        "Formato de entrada",
        "Formato de salida",
    )


def test_detects_required_approval() -> None:
    task = create_task(
        status=TaskStatus.PENDING_APPROVAL,
        plan=(
            "Crear la carpeta",
            "Crear el servicio",
            "Ejecutar las pruebas",
        ),
    )

    assert task.requires_approval
    assert len(task.plan) == 3


@pytest.mark.parametrize(
    "status",
    [
        TaskStatus.CANCELLED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    ],
)
def test_detects_terminal_status(
    status: TaskStatus,
) -> None:
    task = create_task(status=status)

    assert task.is_terminal


def test_normalizes_task_text() -> None:
    task = TaskRecord(
        id=1,
        project_id=1,
        session_id=1,
        source_message_id="  mensaje-1  ",
        title="  Crear proyecto  ",
        description="  Descripción  ",
        target_project_name="  proyecto  ",
        status=TaskStatus.PENDING_PLANNING,
        missing_information=(
            "  ",
            " Formato ",
        ),
        plan=(
            " Paso 1 ",
            "",
        ),
        created_at="fecha",
        updated_at="fecha",
        authorized_at=None,
        completed_at=None,
    )

    assert (
        task.source_message_id
        == "mensaje-1"
    )
    assert task.title == "Crear proyecto"
    assert task.description == "Descripción"
    assert (
        task.target_project_name
        == "proyecto"
    )
    assert task.missing_information == (
        "Formato",
    )
    assert task.plan == ("Paso 1",)


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        (
            "id",
            0,
            "id debe ser mayor que cero",
        ),
        (
            "project_id",
            0,
            (
                "project_id debe ser "
                "mayor que cero"
            ),
        ),
        (
            "session_id",
            0,
            (
                "session_id debe ser "
                "mayor que cero"
            ),
        ),
    ],
)
def test_rejects_invalid_identifiers(
    field_name: str,
    field_value: int,
    message: str,
) -> None:
    values = {
        "id": 1,
        "project_id": 1,
        "session_id": 1,
    }

    values[field_name] = field_value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        TaskRecord(
            id=values["id"],
            project_id=values["project_id"],
            session_id=values["session_id"],
            source_message_id="mensaje",
            title="Título",
            description="Descripción",
            target_project_name=None,
            status=(
                TaskStatus.PENDING_PLANNING
            ),
            missing_information=(),
            plan=(),
            created_at="fecha",
            updated_at="fecha",
            authorized_at=None,
            completed_at=None,
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
        TaskRecord(
            id=1,
            project_id=1,
            session_id=1,
            source_message_id=(
                values["source_message_id"]
            ),
            title=values["title"],
            description=(
                values["description"]
            ),
            target_project_name=None,
            status=(
                TaskStatus.PENDING_PLANNING
            ),
            missing_information=(),
            plan=(),
            created_at="fecha",
            updated_at="fecha",
            authorized_at=None,
            completed_at=None,
        )