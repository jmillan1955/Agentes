from __future__ import annotations

import json
from unittest.mock import Mock

from app.execution.action_generator import (
    ExecutionActionGenerationError,
    ExecutionActionGenerator,
)
from app.execution.actions import (
    ExecutionActionType,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.planning import (
    PlanStatus,
    TaskPlan,
)
from app.providers.base import (
    LanguageResponse,
)
from dataclasses import replace

import pytest

class FakeLanguageProvider:
    def __init__(
        self,
        response_text: str,
    ) -> None:
        self._response_text = response_text
        self.prompt: str | None = None
        self.system_prompt: str | None = None
        self.response_format: (
            str | None
        ) = None
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: str | None = None,
    ) -> LanguageResponse:
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.response_format = (
            response_format
        )

        return LanguageResponse(
            text=self._response_text,
            model="modelo-de-prueba",
            elapsed_seconds=1.25,
        )


def create_approved_plan() -> TaskPlan:
    return TaskPlan(
        id=7,
        task_id=3,
        version=1,
        status=PlanStatus.APPROVED,
        objective=(
            "Crear una aplicacion web para "
            "controlar partidos de padel"
        ),
        scope=(
            "Crear el motor de puntuacion",
            "Crear una API",
        ),
        technologies=(
            "Python",
            "FastAPI",
            "pytest",
        ),
        interfaces=(
            "API REST",
        ),
        inputs=(
            "Equipo que gana el punto",
        ),
        outputs=(
            "Marcador actualizado",
        ),
        data_entities=(
            "Partido",
            "Equipo",
        ),
        business_rules=(
            "Aplicar la puntuacion reglamentaria",
        ),
        phases=(
            "Crear el motor de puntuacion",
            "Crear las pruebas",
        ),
        tests=(
            "Probar juegos y sets",
        ),
        deployment=(
            "Ejecucion local inicial",
        ),
        pending_decisions=(),
        excluded_items=(
            "No modificar archivos externos",
        ),
        completion_criteria=(
            "Las pruebas deben completarse",
        ),
        created_at="2026-08-28T05:00:00Z",
        updated_at="2026-08-28T05:00:00Z",
    )


def test_generates_and_persists_manifest() -> None:
    response_text = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": (
                        "Crear paquete principal"
                    ),
                    "action_type": (
                        "create_directory"
                    ),
                    "relative_path": "app",
                    "content": None,
                },
                {
                    "step_number": 2,
                    "name": (
                        "Crear motor de puntuacion"
                    ),
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "app/scoring.py"
                    ),
                    "content": (
                        "def add_point(score):\n"
                        "    return score + 1\n"
                    ),
                },
                {
                    "step_number": 3,
                    "name": (
                        "Crear pruebas del motor"
                    ),
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "tests/test_scoring.py"
                    ),
                    "content": (
                        "from app.scoring import "
                        "add_point\n\n"
                        "def test_add_point():\n"
                        "    assert add_point(0) == 1\n"
                    ),
                },
                {
                    "step_number": 4,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    provider = FakeLanguageProvider(
        response_text
    )
    manifest_service = Mock()
    stored_manifest = object()

    manifest_service.create.return_value = (
        stored_manifest
    )

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(
            max_actions=10,
        ),
    )

    result = generator.generate(
        execution_id=5,
        plan=create_approved_plan(),
    )

    assert result.manifest is stored_manifest
    assert result.model == "modelo-de-prueba"
    assert result.elapsed_seconds == 1.25
    assert len(result.actions) == 4

    first = result.actions[0]

    assert first.step_number == 1
    assert (
        first.action_type
        == ExecutionActionType.CREATE_DIRECTORY
    )
    assert first.relative_path == "app"

    second = result.actions[1]

    assert (
        second.action_type
        == ExecutionActionType.WRITE_TEXT_FILE
    )
    assert (
        second.relative_path
        == "app/scoring.py"
    )
    assert second.content is not None

    last = result.actions[-1]

    assert (
        last.action_type
        == ExecutionActionType.RUN_PYTEST
    )
    assert last.relative_path == "tests"

    manifest_service.create.assert_called_once_with(
        execution_id=5,
        actions=result.actions,
    )

    assert provider.system_prompt is not None
    assert provider.response_format == "json"
    assert "JSON" in provider.system_prompt
    assert (
        "pytest desde la raiz del workspace"
        in provider.system_prompt
    )
    assert (
        "No utilices una estructura src"
        in provider.system_prompt
    )
    assert provider.prompt is not None
    assert (
        create_approved_plan().objective
        in provider.prompt
    )

@pytest.mark.parametrize(
    "unsafe_path",
    (
        "../fuera.py",
        "tests/../../fuera.py",
        "/ruta/absoluta.py",
        r"C:\ruta\absoluta.py",
        r"..\fuera.py",
    ),
)
def test_rejects_unsafe_paths(
    unsafe_path: str,
) -> None:
    response_text = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Escribir fuera",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": unsafe_path,
                    "content": "contenido",
                },
                {
                    "step_number": 2,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    generator = ExecutionActionGenerator(
        language_provider=(
            FakeLanguageProvider(
                response_text
            )
        ),
        manifest_service=Mock(),
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match=(
            "rutas absolutas|fuera del "
            "workspace"
        ),
    ):
        generator.generate(
            execution_id=5,
            plan=create_approved_plan(),
        )


def test_rejects_invalid_json() -> None:
    generator = ExecutionActionGenerator(
        language_provider=(
            FakeLanguageProvider(
                "esto no es JSON"
            )
        ),
        manifest_service=Mock(),
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="JSON valido",
    ):
        generator.generate(
            execution_id=5,
            plan=create_approved_plan(),
        )


def test_rejects_unapproved_plan() -> None:
    provider = FakeLanguageProvider(
        '{"actions": []}'
    )
    manifest_service = Mock()

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    unapproved_plan = replace(
        create_approved_plan(),
        status=PlanStatus.PENDING_APPROVAL,
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="plan aprobado",
    ):
        generator.generate(
            execution_id=5,
            plan=unapproved_plan,
        )

    assert provider.prompt is None
    manifest_service.create.assert_not_called()


def test_rejects_pending_decisions() -> None:
    provider = FakeLanguageProvider(
        '{"actions": []}'
    )
    manifest_service = Mock()

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    incomplete_plan = replace(
        create_approved_plan(),
        pending_decisions=(
            "Elegir la base de datos",
        ),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="decisiones pendientes",
    ):
        generator.generate(
            execution_id=5,
            plan=incomplete_plan,
        )

    assert provider.prompt is None
    manifest_service.create.assert_not_called()


def test_rejects_too_many_actions() -> None:
    response_text = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Crear archivo",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": "app.py",
                    "content": "value = 1\n",
                },
                {
                    "step_number": 2,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    manifest_service = Mock()

    generator = ExecutionActionGenerator(
        language_provider=(
            FakeLanguageProvider(
                response_text
            )
        ),
        manifest_service=manifest_service,
        limits=ExecutionLimits(
            max_actions=1,
        ),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="maximo de acciones",
    ):
        generator.generate(
            execution_id=5,
            plan=create_approved_plan(),
        )

    manifest_service.create.assert_not_called()


def test_requires_pytest_as_last_action() -> None:
    response_text = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
                {
                    "step_number": 2,
                    "name": "Modificar despues",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": "app.py",
                    "content": "value = 1\n",
                },
            ]
        }
    )

    manifest_service = Mock()

    generator = ExecutionActionGenerator(
        language_provider=(
            FakeLanguageProvider(
                response_text
            )
        ),
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match=(
            "ultima accion debe ser "
            "run_pytest"
        ),
    ):
        generator.generate(
            execution_id=5,
            plan=create_approved_plan(),
        )

    manifest_service.create.assert_not_called()


def test_retries_invalid_model_response(
) -> None:
    invalid_response = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Crear raiz",
                    "action_type": (
                        "create_directory"
                    ),
                    "relative_path": "",
                    "content": None,
                },
                {
                    "step_number": 2,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    corrected_response = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Crear modulo",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": "suma.py",
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    ),
                },
                {
                    "step_number": 2,
                    "name": "Crear pruebas",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    ),
                },
                {
                    "step_number": 3,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    provider = Mock()

    provider.generate.side_effect = (
        LanguageResponse(
            text=invalid_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.5,
        ),
        LanguageResponse(
            text=corrected_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.75,
        ),
    )

    manifest_service = Mock()
    stored_manifest = object()

    manifest_service.create.return_value = (
        stored_manifest
    )

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    result = generator.generate(
        execution_id=5,
        plan=create_approved_plan(),
    )

    assert result.manifest is stored_manifest
    assert len(result.actions) == 3
    assert result.elapsed_seconds == 1.25

    assert provider.generate.call_count == 2
    assert (
        "relative_path no puede estar vacio"
        in provider.generate.call_args_list[
            1
        ].kwargs["prompt"]
    )
    assert (
        "Corrige la respuesta anterior"
        in provider.generate.call_args_list[
            1
        ].kwargs["prompt"]
    )

    manifest_service.create.assert_called_once_with(
        execution_id=5,
        actions=result.actions,
    )

def test_does_not_persist_after_two_invalid_responses(
) -> None:
    invalid_response = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Ruta invalida",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": "",
                    "content": "contenido",
                },
                {
                    "step_number": 2,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": "tests",
                    "content": None,
                },
            ]
        }
    )

    provider = Mock()

    provider.generate.side_effect = (
        LanguageResponse(
            text=invalid_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.5,
        ),
        LanguageResponse(
            text=invalid_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.5,
        ),
    )

    manifest_service = Mock()

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match=(
            "relative_path no puede estar "
            "vacio"
        ),
    ):
        generator.generate(
            execution_id=5,
            plan=create_approved_plan(),
        )

    assert provider.generate.call_count == 2
    manifest_service.create.assert_not_called()


def test_retries_unresolvable_generated_import(
) -> None:
    invalid_response = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Crear paquete",
                    "action_type": (
                        "create_directory"
                    ),
                    "relative_path": "suma",
                    "content": None,
                },
                {
                    "step_number": 2,
                    "name": "Crear modulo",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "suma/suma.py"
                    ),
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    ),
                },
                {
                    "step_number": 3,
                    "name": "Crear prueba",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    ),
                },
                {
                    "step_number": 4,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": ".",
                    "content": None,
                },
            ]
        }
    )

    corrected_response = json.dumps(
        {
            "actions": [
                {
                    "step_number": 1,
                    "name": "Crear modulo",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": "suma.py",
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    ),
                },
                {
                    "step_number": 2,
                    "name": "Crear prueba",
                    "action_type": (
                        "write_text_file"
                    ),
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    ),
                },
                {
                    "step_number": 3,
                    "name": "Ejecutar pruebas",
                    "action_type": "run_pytest",
                    "relative_path": ".",
                    "content": None,
                },
            ]
        }
    )

    provider = Mock()

    provider.generate.side_effect = (
        LanguageResponse(
            text=invalid_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.5,
        ),
        LanguageResponse(
            text=corrected_response,
            model="modelo-de-prueba",
            elapsed_seconds=0.5,
        ),
    )

    manifest_service = Mock()
    manifest_service.create.return_value = (
        object()
    )

    generator = ExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    result = generator.generate(
        execution_id=5,
        plan=create_approved_plan(),
    )

    assert provider.generate.call_count == 2
    assert len(result.actions) == 3
    assert (
        result.actions[0].relative_path
        == "suma.py"
    )
    assert (
        "no puede importarse"
        in provider.generate.call_args_list[
            1
        ].kwargs["prompt"]
    )

    manifest_service.create.assert_called_once()