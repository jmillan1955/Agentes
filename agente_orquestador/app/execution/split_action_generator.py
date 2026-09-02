from __future__ import annotations
import ast
from pathlib import PurePosixPath

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.action_generator import (
    ExecutionActionGenerationError,
    ExecutionActionGenerationResult,
    ExecutionActionGenerator,
)
import json
import logging
import re
from dataclasses import dataclass, field

from app.planning import TaskPlan
from app.providers.base import (
    LanguageProviderError,
)


logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class GeneratedFileSpec:
    relative_path: str
    purpose: str


@dataclass(frozen=True, slots=True)
class GeneratedFilePlan:
    files: tuple[GeneratedFileSpec, ...]
    pytest_target: str


@dataclass(slots=True)
class _GenerationCheckpoint:
    plan_id: int
    file_plan: GeneratedFilePlan
    generated_files: dict[str, str] = field(
        default_factory=dict
    )
    model: str = "unknown"
    elapsed_seconds: float = 0.0


class SplitExecutionActionGenerator(
    ExecutionActionGenerator
):
    _FILE_PLAN_ROOT_KEYS = {
        "files",
        "pytest_target",
    }

    _FILE_SPEC_KEYS = {
        "relative_path",
        "purpose",
    }
    _FILE_CONTENT_ROOT_KEYS = {
        "content",
    }

    @staticmethod
    def _build_file_plan_system_prompt(
    ) -> str:
        return (
            "Devuelve exclusivamente JSON valido.\n"
            "La raiz debe contener exactamente "
            "files y pytest_target.\n"
            "files debe incluir solamente "
            "relative_path y purpose.\n"
            "No incluyas el contenido de los "
            "archivos.\n"
            "No incluyas directorios como "
            "archivos.\n"
            "Las rutas deben ser relativas, "
            "seguras y no pueden repetirse.\n"
            "Para proyectos Python sencillos, "
            "coloca los modulos importables en "
            "la raiz y las pruebas en tests.\n"
            "pytest_target debe ser la ruta desde "
            "la que se ejecutaran las pruebas.\n"
            "No utilices Markdown ni texto "
            "adicional."
        )

    @staticmethod
    def _serialize_plan(
        plan: TaskPlan,
    ) -> str:
        return json.dumps(
            {
                "plan_id": plan.id,
                "task_id": plan.task_id,
                "objective": plan.objective,
                "scope": plan.scope,
                "technologies": (
                    plan.technologies
                ),
                "interfaces": plan.interfaces,
                "inputs": plan.inputs,
                "outputs": plan.outputs,
                "business_rules": (
                    plan.business_rules
                ),
                "phases": plan.phases,
                "tests": plan.tests,
                "deployment": plan.deployment,
                "excluded_items": (
                    plan.excluded_items
                ),
                "completion_criteria": (
                    plan.completion_criteria
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    def _build_file_plan_prompt(
        self,
        plan: TaskPlan,
    ) -> str:
        return (
            "Define solamente los archivos "
            "necesarios para ejecutar este plan. "
            "No generes todavia su contenido.\n\n"
            + self._serialize_plan(plan)
        )

    @staticmethod
    def _build_file_content_system_prompt(
    ) -> str:
        return (
            "Devuelve exclusivamente un objeto "
            "JSON valido con exactamente una "
            "propiedad: content.\n"
            "content debe contener el texto "
            "completo de un unico archivo.\n"
            "No utilices Markdown, explicaciones "
            "ni propiedades adicionales.\n"
            "El archivo debe ser coherente con "
            "las rutas y archivos indicados.\n"
            "El codigo Python debe poder "
            "importarse al ejecutar pytest desde "
            "la raiz del workspace."
        )

    @staticmethod
    def _compact_plan_context(
        plan: TaskPlan,
        max_characters: int = 7000,
    ) -> dict[str, object]:
        context: dict[str, object] = {
            "objective": plan.objective,
            "interfaces": plan.interfaces,
            "business_rules": (
                plan.business_rules
            ),
            "tests": plan.tests,
            "completion_criteria": (
                plan.completion_criteria
            ),
        }

        while (
            len(
                json.dumps(
                    context,
                    ensure_ascii=False,
                )
            )
            > max_characters
        ):
            shortened = False

            for key in (
                "tests",
                "business_rules",
                "completion_criteria",
                "interfaces",
            ):
                values = context[key]

                if (
                    isinstance(values, tuple)
                    and len(values) > 1
                ):
                    context[key] = values[:-1]
                    shortened = True
                    break

            if not shortened:
                objective = str(
                    context["objective"]
                )
                context["objective"] = (
                    objective[:max_characters]
                )
                break

        return context

    @staticmethod
    def _compact_generated_files(
        generated_files: dict[str, str],
        max_characters: int = 6500,
    ) -> list[dict[str, str]]:
        python_files = [
            (path, content)
            for path, content
            in generated_files.items()
            if (
                path.lower().endswith(".py")
                and not SplitExecutionActionGenerator
                ._is_test_path(path)
            )
        ]

        if not python_files:
            return []

        characters_per_file = max(
            1,
            max_characters // len(python_files),
        )

        return [
            {
                "relative_path": path,
                "content_excerpt": content[
                    :characters_per_file
                ],
            }
            for path, content in python_files
        ]

    def _build_file_content_prompt(
        self,
        plan: TaskPlan,
        file_plan: GeneratedFilePlan,
        file_spec: GeneratedFileSpec,
        generated_files: dict[str, str],
    ) -> str:
        context = {
            "approved_plan": (
                self._compact_plan_context(plan)
            ),
            "planned_files": [
                {
                    "relative_path": (
                        planned.relative_path
                    ),
                    "purpose": planned.purpose,
                }
                for planned in file_plan.files
            ],
            "target_file": {
                "relative_path": (
                    file_spec.relative_path
                ),
                "purpose": file_spec.purpose,
            },
            "previous_file_excerpts": (
                self._compact_generated_files(
                    generated_files
                )
            ),
            "pytest_target": (
                file_plan.pytest_target
            ),
        }

        return (
            "Genera solamente el contenido "
            "completo del archivo target_file.\n\n"
            + json.dumps(
                context,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    def generate(
        self,
        execution_id: int,
        plan: TaskPlan,
    ) -> ExecutionActionGenerationResult:
        if execution_id <= 0:
            raise ExecutionActionGenerationError(
                "El identificador de ejecucion "
                "debe ser mayor que cero"
            )

        self._validate_plan(plan)

        checkpoints = getattr(
            self,
            "_generation_checkpoints",
            None,
        )
        if checkpoints is None:
            checkpoints = {}
            self._generation_checkpoints = (
                checkpoints
            )

        checkpoint = checkpoints.get(
            execution_id
        )

        if (
            checkpoint is None
            or checkpoint.plan_id != plan.id
        ):
            (
                file_plan,
                model,
                elapsed_seconds,
            ) = self._request_file_plan(plan)

            checkpoint = _GenerationCheckpoint(
                plan_id=plan.id,
                file_plan=file_plan,
                model=model,
                elapsed_seconds=elapsed_seconds,
            )
            checkpoints[execution_id] = checkpoint
        else:
            file_plan = checkpoint.file_plan
            logger.info(
                "Reanudando manifiesto de la "
                "ejecucion %s con %s archivos "
                "ya generados",
                execution_id,
                len(checkpoint.generated_files),
            )

        ordered_files = tuple(
            sorted(
                file_plan.files,
                key=lambda item: (
                    self._is_test_path(
                        item.relative_path
                    ),
                    item.relative_path,
                ),
            )
        )

        for index, file_spec in enumerate(
            ordered_files,
            start=1,
        ):
            if (
                file_spec.relative_path
                in checkpoint.generated_files
            ):
                logger.info(
                    "Reutilizando archivo %s/%s: %s",
                    index,
                    len(ordered_files),
                    file_spec.relative_path,
                )
                continue

            logger.info(
                "Generando archivo %s/%s: %s",
                index,
                len(ordered_files),
                file_spec.relative_path,
            )

            try:
                (
                    content,
                    response_model,
                    response_elapsed,
                ) = self._request_file_content(
                    plan=plan,
                    file_plan=file_plan,
                    file_spec=file_spec,
                    generated_files=(
                        checkpoint.generated_files
                    ),
                )
            except (
                LanguageProviderError,
                ExecutionActionGenerationError,
            ) as error:
                logger.exception(
                    "Fallo al generar el archivo %s",
                    file_spec.relative_path,
                )
                raise ExecutionActionGenerationError(
                    "No se pudo generar el archivo "
                    f"'{file_spec.relative_path}': "
                    f"{error}"
                ) from error

            checkpoint.generated_files[
                file_spec.relative_path
            ] = content
            checkpoint.model = response_model
            checkpoint.elapsed_seconds += (
                response_elapsed
            )

            logger.info(
                "Archivo generado %s/%s: %s",
                index,
                len(ordered_files),
                file_spec.relative_path,
            )

        actions = self._build_actions(
            file_plan=file_plan,
            ordered_files=ordered_files,
            generated_files=(
                checkpoint.generated_files
            ),
        )

        self._validate_unique_write_paths(
            actions
        )
        self._validate_python_actions(
            actions
        )

        manifest = self._manifest_service.create(
            execution_id=execution_id,
            actions=actions,
        )

        checkpoints.pop(execution_id, None)

        return ExecutionActionGenerationResult(
            manifest=manifest,
            actions=actions,
            model=checkpoint.model,
            elapsed_seconds=(
                checkpoint.elapsed_seconds
            ),
        )

    def _parse_file_plan(
        self,
        response_text: str,
    ) -> GeneratedFilePlan:
        json_text = self._extract_json(
            response_text
        )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as error:
            raise ExecutionActionGenerationError(
                "El plan de archivos no contiene "
                "un JSON valido"
            ) from error

        if not isinstance(data, dict):
            raise ExecutionActionGenerationError(
                "El plan de archivos debe ser "
                "un objeto JSON"
            )

        if set(data) != self._FILE_PLAN_ROOT_KEYS:
            raise ExecutionActionGenerationError(
                "El plan de archivos debe contener "
                "solamente files y pytest_target"
            )

        file_values = data["files"]
        pytest_target = data["pytest_target"]

        if (
            not isinstance(file_values, list)
            or not file_values
        ):
            raise ExecutionActionGenerationError(
                "files debe ser una lista "
                "no vacia"
            )

        if (
            not isinstance(pytest_target, str)
            or not pytest_target.strip()
        ):
            raise ExecutionActionGenerationError(
                "pytest_target debe ser texto "
                "no vacio"
            )

        self._validate_relative_path(
            pytest_target
        )

        files: list[GeneratedFileSpec] = []
        known_paths: set[str] = set()

        for value in file_values:
            if (
                not isinstance(value, dict)
                or set(value)
                != self._FILE_SPEC_KEYS
            ):
                raise ExecutionActionGenerationError(
                    "Cada archivo debe contener "
                    "solamente relative_path "
                    "y purpose"
                )

            relative_path = value[
                "relative_path"
            ]
            purpose = value["purpose"]

            if (
                not isinstance(relative_path, str)
                or not relative_path.strip()
            ):
                raise ExecutionActionGenerationError(
                    "La ruta del archivo debe ser "
                    "texto no vacio"
                )

            if (
                not isinstance(purpose, str)
                or not purpose.strip()
            ):
                raise ExecutionActionGenerationError(
                    "El proposito del archivo debe "
                    "ser texto no vacio"
                )

            self._validate_relative_path(
                relative_path
            )

            normalized_path = (
                relative_path.strip()
                .replace("\\", "/")
            )

            if normalized_path == ".":
                raise ExecutionActionGenerationError(
                    "La ruta de un archivo no puede "
                    "ser la raiz del workspace"
                )

            if normalized_path in known_paths:
                raise ExecutionActionGenerationError(
                    "El plan contiene una ruta "
                    "de archivo duplicada: "
                    f"{normalized_path}"
                )

            known_paths.add(normalized_path)

            files.append(
                GeneratedFileSpec(
                    relative_path=normalized_path,
                    purpose=purpose.strip(),
                )
            )

        return GeneratedFilePlan(
            files=tuple(files),
            pytest_target=(
                pytest_target.strip()
                .replace("\\", "/")
            ),
        )

    def _parse_file_content(
        self,
        response_text: str,
    ) -> str:
        json_text = self._extract_json(
            response_text
        )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as error:
            raise ExecutionActionGenerationError(
                "El contenido del archivo no "
                "contiene un JSON valido"
            ) from error

        if not isinstance(data, dict):
            raise ExecutionActionGenerationError(
                "El contenido del archivo debe "
                "ser un objeto JSON"
            )

        if (
            set(data)
            != self._FILE_CONTENT_ROOT_KEYS
        ):
            raise ExecutionActionGenerationError(
                "La respuesta debe contener "
                "solamente content"
            )

        content = data["content"]

        if not isinstance(content, str):
            raise ExecutionActionGenerationError(
                "content debe ser texto"
            )

        if (
            len(content.encode("utf-8"))
            > self._limits.max_text_file_bytes
        ):
            raise ExecutionActionGenerationError(
                "El contenido del archivo supera "
                "el limite permitido"
            )

        return content

    @staticmethod
    def _complete_file_plan_from_plan(
        plan: TaskPlan,
        file_plan: GeneratedFilePlan,
    ) -> GeneratedFilePlan:
        plan_texts = (
            plan.objective,
            *plan.scope,
            *plan.interfaces,
            *plan.phases,
            *plan.tests,
            *plan.deployment,
            *plan.completion_criteria,
        )
        required_paths: set[str] = set()

        for text in plan_texts:
            required_paths.update(
                match.lower()
                for match in re.findall(
                    (
                        r"\b(?:[A-Za-z0-9_-]+/)*"
                        r"[A-Za-z0-9_-]+"
                        r"\.(?:py|md)\b"
                    ),
                    text,
                    flags=re.IGNORECASE,
                )
            )

        if any(
            "readme" in text.lower()
            for text in plan_texts
        ):
            required_paths.add("readme.md")

        files = list(file_plan.files)
        known_paths = {
            item.relative_path.lower()
            for item in files
        }

        for required_path in sorted(
            required_paths - known_paths
        ):
            output_path = (
                "README.md"
                if required_path == "readme.md"
                else required_path
            )
            files.append(
                GeneratedFileSpec(
                    relative_path=output_path,
                    purpose=(
                        "Crear el archivo exigido "
                        "por el plan aprobado"
                    ),
                )
            )
            known_paths.add(required_path)

        if (
            plan.tests
            and not any(
                SplitExecutionActionGenerator
                ._is_test_path(path)
                for path in known_paths
            )
        ):
            source_candidates = [
                PurePosixPath(path).stem
                for path in sorted(known_paths)
                if (
                    path.endswith(".py")
                    and PurePosixPath(path).name
                    not in {"main.py", "ui.py"}
                )
            ]
            preferred = next(
                (
                    name
                    for name in source_candidates
                    if (
                        "engine" in name
                        or "logic" in name
                    )
                ),
                (
                    source_candidates[0]
                    if source_candidates
                    else "generated_project"
                ),
            )
            test_path = (
                f"tests/test_{preferred}.py"
            )
            files.append(
                GeneratedFileSpec(
                    relative_path=test_path,
                    purpose=(
                        "Probar la logica exigida "
                        "por el plan aprobado sin "
                        "abrir ventanas"
                    ),
                )
            )
            known_paths.add(test_path)

        pytest_target = file_plan.pytest_target
        normalized_target = pytest_target.lower()

        if (
            normalized_target.endswith(".py")
            or normalized_target in known_paths
        ):
            pytest_target = "."

        return GeneratedFilePlan(
            files=tuple(files),
            pytest_target=pytest_target,
        )

    @staticmethod
    def _validate_file_plan_against_plan(
        plan: TaskPlan,
        file_plan: GeneratedFilePlan,
    ) -> None:
        planned_paths = {
            file_spec.relative_path.lower()
            for file_spec in file_plan.files
        }

        if (
            plan.tests
            and not any(
                SplitExecutionActionGenerator
                ._is_test_path(path)
                for path in planned_paths
            )
        ):
            raise ExecutionActionGenerationError(
                "El plan aprobado exige pruebas, "
                "pero no se ha incluido ningun "
                "archivo de tests"
            )

        pytest_target = (
            file_plan.pytest_target.lower()
        )
        if (
            pytest_target.endswith(".py")
            or pytest_target in planned_paths
        ):
            raise ExecutionActionGenerationError(
                "pytest_target debe apuntar a un "
                "directorio, no a un archivo"
            )

        plan_texts = (
            plan.objective,
            *plan.scope,
            *plan.interfaces,
            *plan.phases,
            *plan.tests,
            *plan.deployment,
            *plan.completion_criteria,
        )
        explicit_paths: set[str] = set()

        for text in plan_texts:
            explicit_paths.update(
                match.lower()
                for match in re.findall(
                    (
                        r"\b(?:[A-Za-z0-9_-]+/)*"
                        r"[A-Za-z0-9_-]+"
                        r"\.(?:py|md)\b"
                    ),
                    text,
                    flags=re.IGNORECASE,
                )
            )

        if any(
            "readme" in text.lower()
            for text in plan_texts
        ):
            explicit_paths.add("readme.md")

        missing_paths = sorted(
            explicit_paths - planned_paths
        )

        if missing_paths:
            raise ExecutionActionGenerationError(
                "Faltan archivos exigidos por el "
                "plan aprobado: "
                + ", ".join(missing_paths)
            )

    def _request_file_plan(
        self,
        plan: TaskPlan,
    ) -> tuple[
        GeneratedFilePlan,
        str,
        float,
    ]:
        prompt = self._build_file_plan_prompt(
            plan
        )
        system_prompt = (
            self._build_file_plan_system_prompt()
        )
        total_elapsed = 0.0

        for attempt_number in range(
            1,
            self._MAX_GENERATION_ATTEMPTS + 1,
        ):
            response = (
                self._language_provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_format="json",
                )
            )
            total_elapsed += (
                response.elapsed_seconds
            )

            try:
                file_plan = self._parse_file_plan(
                    response.text
                )
                file_plan = (
                    self
                    ._complete_file_plan_from_plan(
                        plan=plan,
                        file_plan=file_plan,
                    )
                )
                self._validate_file_plan_against_plan(
                    plan=plan,
                    file_plan=file_plan,
                )
            except (
                ExecutionActionGenerationError
            ) as error:
                if (
                    attempt_number
                    >= self._MAX_GENERATION_ATTEMPTS
                ):
                    raise

                prompt = self._build_retry_prompt(
                    original_prompt=(
                        self._build_file_plan_prompt(
                            plan
                        )
                    ),
                    invalid_response=(
                        response.text
                    ),
                    validation_error=str(error),
                )
                continue

            return (
                file_plan,
                response.model,
                total_elapsed,
            )

        raise RuntimeError(
            "No se obtuvo un plan de archivos"
        )

    def _request_file_content(
        self,
        plan: TaskPlan,
        file_plan: GeneratedFilePlan,
        file_spec: GeneratedFileSpec,
        generated_files: dict[str, str],
    ) -> tuple[str, str, float]:
        original_prompt = (
            self._build_file_content_prompt(
                plan=plan,
                file_plan=file_plan,
                file_spec=file_spec,
                generated_files=(
                    generated_files
                ),
            )
        )
        prompt = original_prompt
        system_prompt = (
            self
            ._build_file_content_system_prompt()
        )
        total_elapsed = 0.0

        for attempt_number in range(
            1,
            self._MAX_GENERATION_ATTEMPTS + 1,
        ):
            response = (
                self._language_provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_format="json",
                )
            )
            total_elapsed += (
                response.elapsed_seconds
            )

            try:
                content = (
                    self._parse_file_content(
                        response.text
                    )
                )
                self._validate_file_syntax(
                    file_spec=file_spec,
                    content=content,
                )
            except (
                ExecutionActionGenerationError
            ) as error:
                if (
                    attempt_number
                    >= self._MAX_GENERATION_ATTEMPTS
                ):
                    raise

                prompt = self._build_retry_prompt(
                    original_prompt=(
                        original_prompt
                    ),
                    invalid_response=(
                        response.text
                    ),
                    validation_error=str(error),
                )
                continue

            return (
                content,
                response.model,
                total_elapsed,
            )

        raise RuntimeError(
            "No se obtuvo contenido de archivo"
        )

    def _build_retry_prompt(
        self,
        original_prompt: str,
        invalid_response: str,
        validation_error: str,
    ) -> str:
        response_summary = invalid_response[
            -self
            ._MAX_RETRY_RESPONSE_CHARACTERS:
        ]

        return (
            f"{original_prompt}\n\n"
            "Corrige la respuesta anterior.\n"
            "Error de validacion:\n"
            f"{validation_error}\n\n"
            "Respuesta anterior no valida:\n"
            f"{response_summary}"
        )

    @staticmethod
    def _validate_file_syntax(
        file_spec: GeneratedFileSpec,
        content: str,
    ) -> None:
        if not (
            file_spec.relative_path
            .lower()
            .endswith(".py")
        ):
            return

        try:
            ast.parse(
                content,
                filename=(
                    file_spec.relative_path
                ),
            )
        except SyntaxError as error:
            raise ExecutionActionGenerationError(
                "El archivo Python "
                f"'{file_spec.relative_path}' "
                "contiene sintaxis invalida"
            ) from error

    @staticmethod
    def _is_test_path(
        relative_path: str,
    ) -> bool:
        normalized = relative_path.replace(
            "\\",
            "/",
        )

        return (
            normalized == "tests.py"
            or normalized.startswith("tests/")
            or PurePosixPath(
                normalized
            ).name.startswith("test_")
        )

    def _build_actions(
        self,
        file_plan: GeneratedFilePlan,
        ordered_files: tuple[
            GeneratedFileSpec,
            ...,
        ],
        generated_files: dict[str, str],
    ) -> tuple[ExecutionAction, ...]:
        directories: list[str] = []
        known_directories: set[str] = set()

        for file_spec in ordered_files:
            parent = PurePosixPath(
                file_spec.relative_path
            ).parent
            current_parts: list[str] = []

            for part in parent.parts:
                if part == ".":
                    continue

                current_parts.append(part)
                directory = "/".join(
                    current_parts
                )

                if (
                    directory
                    not in known_directories
                ):
                    known_directories.add(
                        directory
                    )
                    directories.append(directory)

        action_values: list[
            ExecutionAction
        ] = []
        step_number = 1

        for directory in directories:
            action_values.append(
                ExecutionAction(
                    step_number=step_number,
                    name=(
                        "Crear directorio "
                        f"{directory}"
                    ),
                    action_type=(
                        ExecutionActionType
                        .CREATE_DIRECTORY
                    ),
                    relative_path=directory,
                )
            )
            step_number += 1

        for file_spec in ordered_files:
            action_values.append(
                ExecutionAction(
                    step_number=step_number,
                    name=(
                        "Crear archivo "
                        f"{file_spec.relative_path}"
                    ),
                    action_type=(
                        ExecutionActionType
                        .WRITE_TEXT_FILE
                    ),
                    relative_path=(
                        file_spec.relative_path
                    ),
                    content=generated_files[
                        file_spec.relative_path
                    ],
                )
            )
            step_number += 1

        action_values.append(
            ExecutionAction(
                step_number=step_number,
                name="Ejecutar pruebas",
                action_type=(
                    ExecutionActionType.RUN_PYTEST
                ),
                relative_path=(
                    file_plan.pytest_target
                ),
            )
        )

        actions = tuple(action_values)

        if (
            len(actions)
            > self._limits.max_actions
        ):
            raise ExecutionActionGenerationError(
                "El manifiesto supera el numero "
                "maximo de acciones"
            )

        return actions