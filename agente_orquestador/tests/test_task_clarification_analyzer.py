from app.tasks import (
    TaskClarificationAnalyzer,
    TaskRecord,
    TaskStatus,
)


def create_task(
    title: str = (
        "Crea el proyecto agente_audioText"
    ),
    description: str = (
        "Crea el proyecto agente_audioText"
    ),
    target_project_name: str | None = (
        "agente_audioText"
    ),
) -> TaskRecord:
    return TaskRecord(
        id=1,
        project_id=1,
        session_id=1,
        source_message_id="mensaje-1",
        title=title,
        description=description,
        target_project_name=(
            target_project_name
        ),
        status=TaskStatus.PENDING_PLANNING,
        missing_information=(),
        plan=(),
        created_at="fecha",
        updated_at="fecha",
        authorized_at=None,
        completed_at=None,
    )


def test_detects_all_audio_text_information() -> None:
    questions = (
        TaskClarificationAnalyzer()
        .analyze(create_task())
    )

    assert len(questions) == 5
    assert any(
        "formatos de entrada" in question
        for question in questions
    )
    assert any(
        "formato de salida" in question
        for question in questions
    )
    assert any(
        "motor de voz" in question
        for question in questions
    )
    assert any(
        "canal" in question
        for question in questions
    )
    assert any(
        "voz será fija" in question
        for question in questions
    )


def test_detects_no_audio_text_information() -> None:
    task = create_task(
        description=(
            "Recibir TXT por Telegram, "
            "convertirlo a MP3 con Kokoro "
            "y permitir seleccionar voz "
            "en cada conversión"
        )
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert questions == ()


def test_detects_only_missing_output_format() -> None:
    task = create_task(
        description=(
            "Recibir TXT por Telegram, "
            "usar Kokoro y permitir una "
            "voz configurable"
        )
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert len(questions) == 1
    assert (
        "formato de salida"
        in questions[0]
    )


def test_complete_desktop_calculator_needs_no_questions(
) -> None:
    task = create_task(
        title=(
            "Crear calculadora de escritorio"
        ),
        description=(
            "En el proyecto calculadora_tkinter, "
            "crea una aplicación de escritorio "
            "para Windows con Python y Tkinter. "
            "Debe incluir pantalla, botones 0-9, "
            "punto decimal, operadores, igual, C "
            "y retroceso. La lógica debe probarse "
            "con pytest sin abrir una ventana y "
            "debe iniciarse con python main.py."
        ),
        target_project_name=(
            "calculadora_tkinter"
        ),
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert questions == ()


def test_complete_home_assistant_task_needs_no_questions(
) -> None:
    task = create_task(
        title="Crear automatización YAML",
        description=(
            "Crea para Home Assistant una "
            "automatización YAML que encienda "
            "switch.luz cuando binary_sensor."
            "movimiento esté activo y la apague "
            "un minuto después. Debe poder "
            "validarse con las pruebas."
        ),
        target_project_name="home_assistant",
    )

    assert (
        TaskClarificationAnalyzer()
        .analyze(task)
        == ()
    )


def test_incomplete_recipe_application_asks_only_missing(
) -> None:
    task = create_task(
        title="Crear aplicación de recetas",
        description=(
            "Quiero una aplicación para "
            "organizar recetas."
        ),
        target_project_name="recetas",
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert not any(
        "objetivo principal" in question
        for question in questions
    )
    assert any(
        "tipo de aplicación" in question
        for question in questions
    )
    assert any(
        "Quiénes utilizarán" in question
        for question in questions
    )
    assert any(
        "funcionalidades principales" in question
        for question in questions
    )
    assert any(
        "información debe guardar" in question
        for question in questions
    )
    assert any(
        "preferencias tecnológicas" in question
        for question in questions
    )
    assert any(
        "considerar terminada" in question
        for question in questions
    )


def test_minimal_project_does_not_repeat_known_objective(
) -> None:
    task = create_task(
        title="Crea el proyecto puntuacion_padel",
        description=(
            "Crea el proyecto puntuacion_padel"
        ),
        target_project_name=(
            "puntuacion_padel"
        ),
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert not any(
        "objetivo principal" in question
        for question in questions
    )
    assert len(questions) < 8


def test_uses_missing_questions_without_project_name(
) -> None:
    task = create_task(
        title="Nuevo proyecto",
        description="Nuevo proyecto",
        target_project_name=None,
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert any(
        "objetivo principal" in question
        for question in questions
    )
    assert any(
        "tipo de aplicación" in question
        for question in questions
    )


def test_normalizes_audio_text_project_name() -> None:
    task = create_task(
        target_project_name=(
            "  AGENTE_AUDIOTEXT  "
        )
    )

    questions = (
        TaskClarificationAnalyzer()
        .analyze(task)
    )

    assert len(questions) == 5
