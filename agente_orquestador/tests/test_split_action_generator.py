import json
from unittest.mock import Mock

import pytest

from app.execution.action_generator import (
    ExecutionActionGenerationError,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.split_action_generator import (
    GeneratedFilePlan,
    GeneratedFileSpec,
    SplitExecutionActionGenerator,
)
from types import SimpleNamespace
from app.planning import PlanStatus
from app.providers.base import (
    LanguageProviderError,
    LanguageResponse,
)

def create_generator(
) -> SplitExecutionActionGenerator:
    return SplitExecutionActionGenerator(
        language_provider=Mock(),
        manifest_service=Mock(),
        limits=ExecutionLimits(),
    )


def test_parses_file_plan() -> None:
    response = json.dumps(
        {
            "files": [
                {
                    "relative_path": "suma.py",
                    "purpose": (
                        "Implementar la funcion "
                        "sumar"
                    ),
                },
                {
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "purpose": (
                        "Probar la funcion sumar"
                    ),
                },
            ],
            "pytest_target": ".",
        }
    )

    plan = create_generator()._parse_file_plan(
        response
    )

    assert len(plan.files) == 2
    assert (
        plan.files[0].relative_path
        == "suma.py"
    )
    assert (
        plan.files[1].relative_path
        == "tests/test_suma.py"
    )
    assert plan.pytest_target == "."


def test_rejects_duplicate_file_paths(
) -> None:
    response = json.dumps(
        {
            "files": [
                {
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "purpose": "Primera prueba",
                },
                {
                    "relative_path": (
                        "tests/test_suma.py"
                    ),
                    "purpose": "Segunda prueba",
                },
            ],
            "pytest_target": ".",
        }
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="ruta de archivo duplicada",
    ):
        create_generator()._parse_file_plan(
            response
        )


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "../fuera.py",
        "/tmp/fuera.py",
        r"C:\fuera.py",
    ),
)
def test_rejects_unsafe_file_paths(
    unsafe_path: str,
) -> None:
    response = json.dumps(
        {
            "files": [
                {
                    "relative_path": unsafe_path,
                    "purpose": "Ruta insegura",
                }
            ],
            "pytest_target": ".",
        }
    )

    with pytest.raises(
        ExecutionActionGenerationError,
    ):
        create_generator()._parse_file_plan(
            response
        )

def test_parses_file_content() -> None:
    response = json.dumps(
        {
            "content": (
                "def sumar(a, b):\n"
                "    return a + b\n"
            )
        }
    )

    content = (
        create_generator()
        ._parse_file_content(response)
    )

    assert content == (
        "def sumar(a, b):\n"
        "    return a + b\n"
    )


def test_rejects_extra_content_fields(
) -> None:
    response = json.dumps(
        {
            "content": "value = 1\n",
            "explanation": "Texto adicional",
        }
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="solamente content",
    ):
        create_generator()._parse_file_content(
            response
        )


def test_rejects_non_text_content() -> None:
    response = json.dumps(
        {
            "content": None,
        }
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="content debe ser texto",
    ):
        create_generator()._parse_file_content(
            response
        )

def create_plan():
    return SimpleNamespace(
        id=7,
        task_id=3,
        objective="Crear una funcion suma",
        scope=("Crear modulo",),
        technologies=("Python", "pytest"),
        interfaces=(),
        inputs=("Dos numeros",),
        outputs=("La suma",),
        business_rules=(),
        phases=(),
        tests=("Probar suma",),
        deployment=(),
        excluded_items=("No usar red",),
        completion_criteria=(
            "Todas las pruebas pasan",
        ),
        status=PlanStatus.APPROVED,
        pending_decisions=(),
    )


def test_builds_small_file_plan_prompt(
) -> None:
    generator = create_generator()

    system_prompt = (
        generator
        ._build_file_plan_system_prompt()
    )
    prompt = generator._build_file_plan_prompt(
        create_plan()
    )

    assert (
        "No incluyas el contenido"
        in system_prompt
    )
    assert "files y pytest_target" in (
        system_prompt
    )
    assert "Crear una funcion suma" in prompt


def test_builds_single_file_content_prompt(
) -> None:
    generator = create_generator()
    file_spec = GeneratedFileSpec(
        relative_path="tests/test_suma.py",
        purpose="Probar la suma",
    )
    file_plan = GeneratedFilePlan(
        files=(
            GeneratedFileSpec(
                relative_path="suma.py",
                purpose="Implementar la suma",
            ),
            file_spec,
        ),
        pytest_target=".",
    )

    prompt = (
        generator._build_file_content_prompt(
            plan=create_plan(),
            file_plan=file_plan,
            file_spec=file_spec,
            generated_files={
                "suma.py": (
                    "def sumar(a, b):\n"
                    "    return a + b\n"
                )
            },
        )
    )

    assert "tests/test_suma.py" in prompt
    assert "def sumar(a, b)" in prompt
    assert (
        "Genera solamente el contenido"
        in prompt
    )

def test_generates_files_separately(
) -> None:
    provider = Mock()
    provider.generate.side_effect = (
        LanguageResponse(
            text=json.dumps(
                {
                    "files": [
                        {
                            "relative_path": (
                                "suma.py"
                            ),
                            "purpose": (
                                "Implementar sumar"
                            ),
                        },
                        {
                            "relative_path": (
                                "tests/test_suma.py"
                            ),
                            "purpose": (
                                "Probar sumar"
                            ),
                        },
                    ],
                    "pytest_target": ".",
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.2,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.3,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.4,
        ),
    )

    manifest_service = Mock()
    stored_manifest = object()
    manifest_service.create.return_value = (
        stored_manifest
    )

    generator = SplitExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    result = generator.generate(
        execution_id=5,
        plan=create_plan(),
    )

    assert provider.generate.call_count == 3
    assert result.manifest is stored_manifest
    assert result.elapsed_seconds == (
        pytest.approx(0.9)
    )

    assert [
        (
            action.action_type.value,
            action.relative_path,
        )
        for action in result.actions
    ] == [
        ("create_directory", "tests"),
        ("write_text_file", "suma.py"),
        (
            "write_text_file",
            "tests/test_suma.py",
        ),
        ("run_pytest", "."),
    ]

    manifest_service.create.assert_called_once_with(
        execution_id=5,
        actions=result.actions,
    )

    test_prompt = (
        provider.generate.call_args_list[
            2
        ].kwargs["prompt"]
    )

    assert "def sumar(a, b)" in test_prompt

def test_retries_only_invalid_file_content(
) -> None:
    provider = Mock()
    provider.generate.side_effect = (
        LanguageResponse(
            text=json.dumps(
                {
                    "files": [
                        {
                            "relative_path": (
                                "suma.py"
                            ),
                            "purpose": (
                                "Implementar sumar"
                            ),
                        },
                        {
                            "relative_path": (
                                "tests/test_suma.py"
                            ),
                            "purpose": (
                                "Probar sumar"
                            ),
                        },
                    ],
                    "pytest_target": ".",
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "def sumar(a, b)\n"
                        "    return a + b\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        ),
    )

    manifest_service = Mock()
    manifest_service.create.return_value = (
        object()
    )

    generator = SplitExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    result = generator.generate(
        execution_id=5,
        plan=create_plan(),
    )

    assert provider.generate.call_count == 4
    assert len(result.actions) == 4

    correction_prompt = (
        provider.generate.call_args_list[
            2
        ].kwargs["prompt"]
    )

    assert (
        "contiene sintaxis invalida"
        in correction_prompt
    )

    test_prompt = (
        provider.generate.call_args_list[
            3
        ].kwargs["prompt"]
    )

    assert (
        "def sumar(a, b):"
        in test_prompt
    )

    manifest_service.create.assert_called_once()

def test_does_not_persist_invalid_files(
) -> None:
    file_plan_response = LanguageResponse(
        text=json.dumps(
            {
                "files": [
                    {
                        "relative_path": "suma.py",
                        "purpose": (
                            "Implementar sumar"
                        ),
                    },
                    {
                        "relative_path": (
                            "tests/test_suma.py"
                        ),
                        "purpose": (
                            "Probar sumar"
                        ),
                    },
                ],
                "pytest_target": ".",
            }
        ),
        model="modelo-de-prueba",
        elapsed_seconds=0.1,
    )

    invalid_content_response = (
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "def sumar(a, b)\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        )
    )

    provider = Mock()
    provider.generate.side_effect = (
        file_plan_response,
        invalid_content_response,
        invalid_content_response,
        invalid_content_response,
    )

    manifest_service = Mock()

    generator = SplitExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="contiene sintaxis invalida",
    ):
        generator.generate(
            execution_id=5,
            plan=create_plan(),
        )

    assert provider.generate.call_count == 4
    manifest_service.create.assert_not_called()

def test_resumes_after_provider_timeout() -> None:
    provider = Mock()
    provider.generate.side_effect = (
        LanguageResponse(
            text=json.dumps(
                {
                    "files": [
                        {
                            "relative_path": "suma.py",
                            "purpose": "Implementar suma",
                        },
                        {
                            "relative_path": (
                                "tests/test_suma.py"
                            ),
                            "purpose": "Probar suma",
                        },
                    ],
                    "pytest_target": ".",
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.1,
        ),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "def sumar(a, b):\n"
                        "    return a + b\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.2,
        ),
        LanguageProviderError("timeout"),
        LanguageResponse(
            text=json.dumps(
                {
                    "content": (
                        "from suma import sumar\n\n"
                        "def test_sumar():\n"
                        "    assert sumar(2, 3) == 5\n"
                    )
                }
            ),
            model="modelo-de-prueba",
            elapsed_seconds=0.3,
        ),
    )

    manifest_service = Mock()
    manifest_service.create.return_value = object()

    generator = SplitExecutionActionGenerator(
        language_provider=provider,
        manifest_service=manifest_service,
        limits=ExecutionLimits(),
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="tests/test_suma.py",
    ):
        generator.generate(
            execution_id=9,
            plan=create_plan(),
        )

    result = generator.generate(
        execution_id=9,
        plan=create_plan(),
    )

    assert provider.generate.call_count == 4
    assert result.elapsed_seconds == (
        pytest.approx(0.6)
    )
    assert manifest_service.create.call_count == 1


def test_limits_previous_file_context() -> None:
    generator = create_generator()

    compact = generator._compact_generated_files(
        {
            "primero.py": "a" * 5000,
            "segundo.py": "b" * 5000,
        },
        max_characters=6000,
    )

    assert sum(
        len(item["content_excerpt"])
        for item in compact
    ) == 6000
    assert compact[-1]["relative_path"] == (
        "segundo.py"
    )


def test_rejects_file_plan_without_tests() -> None:
    file_plan = GeneratedFilePlan(
        files=(
            GeneratedFileSpec(
                relative_path="suma.py",
                purpose="Implementar suma",
            ),
        ),
        pytest_target=".",
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="archivo de tests",
    ):
        (
            create_generator()
            ._validate_file_plan_against_plan(
                plan=create_plan(),
                file_plan=file_plan,
            )
        )


def test_rejects_python_file_as_pytest_target(
) -> None:
    file_plan = GeneratedFilePlan(
        files=(
            GeneratedFileSpec(
                relative_path="suma.py",
                purpose="Implementar suma",
            ),
            GeneratedFileSpec(
                relative_path="tests/test_suma.py",
                purpose="Probar suma",
            ),
        ),
        pytest_target="suma.py",
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="directorio",
    ):
        (
            create_generator()
            ._validate_file_plan_against_plan(
                plan=create_plan(),
                file_plan=file_plan,
            )
        )


def test_rejects_missing_explicit_plan_files(
) -> None:
    plan = create_plan()
    plan.interfaces = (
        "Arranque en main.py",
        "Interfaz separada en ui.py",
    )
    plan.phases = (
        "Documentar el uso en README",
    )

    file_plan = GeneratedFilePlan(
        files=(
            GeneratedFileSpec(
                relative_path="suma.py",
                purpose="Implementar suma",
            ),
            GeneratedFileSpec(
                relative_path="tests/test_suma.py",
                purpose="Probar suma",
            ),
        ),
        pytest_target=".",
    )

    with pytest.raises(
        ExecutionActionGenerationError,
        match="main.py, readme.md, ui.py",
    ):
        (
            create_generator()
            ._validate_file_plan_against_plan(
                plan=plan,
                file_plan=file_plan,
            )
        )


def test_completes_incomplete_file_plan() -> None:
    plan = create_plan()
    plan.interfaces = (
        "Motor en calculator_engine.py",
        "Arranque en main.py",
        "Interfaz en ui.py",
    )
    plan.phases = (
        "Documentar el proyecto en README",
    )

    incomplete = GeneratedFilePlan(
        files=(
            GeneratedFileSpec(
                relative_path="calculator_engine.py",
                purpose="Implementar el motor",
            ),
            GeneratedFileSpec(
                relative_path="main.py",
                purpose="Arrancar la aplicacion",
            ),
            GeneratedFileSpec(
                relative_path="ui.py",
                purpose="Crear la interfaz",
            ),
        ),
        pytest_target="calculator_engine.py",
    )

    completed = (
        create_generator()
        ._complete_file_plan_from_plan(
            plan=plan,
            file_plan=incomplete,
        )
    )

    assert {
        item.relative_path
        for item in completed.files
    } == {
        "calculator_engine.py",
        "main.py",
        "ui.py",
        "readme.md",
        "tests/test_calculator_engine.py",
    }
    assert completed.pytest_target == "."

    (
        create_generator()
        ._validate_file_plan_against_plan(
            plan=plan,
            file_plan=completed,
        )
    )
