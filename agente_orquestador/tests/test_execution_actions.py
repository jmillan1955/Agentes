import pytest

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)


def test_creates_directory_action() -> None:
    action = ExecutionAction(
        step_number=1,
        name=" Crear directorio ",
        action_type=(
            ExecutionActionType
            .CREATE_DIRECTORY
        ),
        relative_path=" src ",
    )

    assert action.step_number == 1
    assert action.name == "Crear directorio"
    assert action.relative_path == "src"
    assert action.content is None


def test_creates_write_file_action() -> None:
    action = ExecutionAction(
        step_number=2,
        name="Crear modulo",
        action_type=(
            ExecutionActionType
            .WRITE_TEXT_FILE
        ),
        relative_path="src/main.py",
        content="print('hola')\n",
    )

    assert (
        action.action_type
        == ExecutionActionType.WRITE_TEXT_FILE
    )
    assert action.content == "print('hola')\n"


@pytest.mark.parametrize(
    "field_name",
    (
        "name",
        "relative_path",
    ),
)
def test_rejects_empty_text(
    field_name: str,
) -> None:
    values = {
        "name": "Crear directorio",
        "relative_path": "src",
    }
    values[field_name] = "   "

    with pytest.raises(ValueError):
        ExecutionAction(
            step_number=1,
            **values,
            action_type=(
                ExecutionActionType
                .CREATE_DIRECTORY
            ),
        )


def test_rejects_content_for_directory() -> None:
    with pytest.raises(
        ValueError,
        match="no admite contenido",
    ):
        ExecutionAction(
            step_number=1,
            name="Crear directorio",
            action_type=(
                ExecutionActionType
                .CREATE_DIRECTORY
            ),
            relative_path="src",
            content="contenido",
        )


def test_requires_content_for_file() -> None:
    with pytest.raises(
        ValueError,
        match="requiere contenido",
    ):
        ExecutionAction(
            step_number=1,
            name="Crear archivo",
            action_type=(
                ExecutionActionType
                .WRITE_TEXT_FILE
            ),
            relative_path="README.md",
        )

def test_creates_pytest_action() -> None:
    action = ExecutionAction(
        step_number=3,
        name="Ejecutar pruebas",
        action_type=(
            ExecutionActionType.RUN_PYTEST
        ),
        relative_path="tests",
    )

    assert (
        action.action_type
        == ExecutionActionType.RUN_PYTEST
    )
    assert action.relative_path == "tests"
    assert action.content is None


def test_rejects_content_for_pytest() -> None:
    with pytest.raises(
        ValueError,
        match="run_pytest no admite",
    ):
        ExecutionAction(
            step_number=3,
            name="Ejecutar pruebas",
            action_type=(
                ExecutionActionType.RUN_PYTEST
            ),
            relative_path="tests",
            content="comando arbitrario",
        )