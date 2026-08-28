from __future__ import annotations

import json
import re
import ast
from dataclasses import dataclass
from pathlib import (
    PurePosixPath,
    PureWindowsPath,
)
from typing import Any

from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.manifest_models import (
    ExecutionManifest,
)
from app.execution.manifest_service import (
    ExecutionManifestService,
)
from app.planning import (
    PlanStatus,
    TaskPlan,
)
from app.providers.base import (
    LanguageProvider,
)


class ExecutionActionGenerationError(
    ValueError
):
    """No se pudo generar un manifiesto seguro."""


@dataclass(frozen=True, slots=True)
class ExecutionActionGenerationResult:
    manifest: ExecutionManifest
    actions: tuple[ExecutionAction, ...]
    model: str
    elapsed_seconds: float


class ExecutionActionGenerator:
    _JSON_BLOCK_PATTERN = re.compile(
        r"```(?:json)?\s*(.*?)\s*```",
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    _ROOT_KEYS = {
        "actions",
    }

    _ACTION_REQUIRED_KEYS = {
        "step_number",
        "name",
        "action_type",
        "relative_path",
    }

    _ACTION_OPTIONAL_KEYS = {
        "content",
    }

    _MAX_GENERATION_ATTEMPTS = 3
    _MAX_RETRY_RESPONSE_CHARACTERS = 6000

    def __init__(
        self,
        language_provider: LanguageProvider,
        manifest_service: (
            ExecutionManifestService
        ),
        limits: ExecutionLimits,
    ) -> None:
        self._language_provider = (
            language_provider
        )
        self._manifest_service = (
            manifest_service
        )
        self._limits = limits

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

        prompt = self._build_prompt(plan)
        system_prompt = (
            self._build_system_prompt()
        )

        total_elapsed_seconds = 0.0
        actions = None
        response = None

        for attempt_number in range(
            1,
            self._MAX_GENERATION_ATTEMPTS + 1,
        ):
            response = (
                self._language_provider.generate(
                    prompt=prompt,
                    system_prompt=(
                        system_prompt
                    ),
                    response_format="json",
                )
            )

            total_elapsed_seconds += (
                response.elapsed_seconds
            )

            try:
                actions = self._parse_actions(
                    response.text
                )

            except (
                ExecutionActionGenerationError
            ) as error:
                if (
                    attempt_number
                    >= self
                    ._MAX_GENERATION_ATTEMPTS
                ):
                    raise

                prompt = (
                    self._build_correction_prompt(
                        plan=plan,
                        invalid_response=(
                            response.text
                        ),
                        validation_error=(
                            str(error)
                        ),
                    )
                )

                continue

            break

        if actions is None or response is None:
            raise RuntimeError(
                "No se obtuvo un manifiesto"
            )

        manifest = self._manifest_service.create(
            execution_id=execution_id,
            actions=actions,
        )

        return ExecutionActionGenerationResult(
            manifest=manifest,
            actions=actions,
            model=response.model,
            elapsed_seconds=(
                total_elapsed_seconds
            ),
        )

    @staticmethod
    def _validate_plan(
        plan: TaskPlan,
    ) -> None:
        if plan.status != PlanStatus.APPROVED:
            raise ExecutionActionGenerationError(
                "Solo puede generarse un "
                "manifiesto desde un plan "
                "aprobado"
            )

        if plan.pending_decisions:
            raise ExecutionActionGenerationError(
                "El plan contiene decisiones "
                "pendientes"
            )

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Devuelve exclusivamente un objeto "
            "JSON valido.\n"
            "No utilices Markdown, comentarios "
            "ni texto adicional.\n"
            "La raiz del objeto JSON debe tener "
            "exactamente una unica propiedad: "
            "actions.\n"
            "No incluyas propiedades como status, "
            "message, explanation, reasoning, "
            "summary ni ninguna otra.\n"
            "El formato obligatorio de la raiz es: "
            '{"actions": [...]}\n'
            "Cada accion debe contener: "
            "step_number, name, action_type, "
            "relative_path y content.\n"
            "Los unicos action_type permitidos "
            "son create_directory, "
            "write_text_file y run_pytest.\n"
            "Todas las rutas deben ser relativas "
            "al workspace.\n"
            "relative_path nunca puede estar "
            "vacio.\n"
            "Para representar la raiz del "
            "workspace utiliza un punto, pero "
            "no crees la raiz porque ya existe.\n"
            "No utilices rutas absolutas, .., "
            "comandos de sistema, enlaces ni "
            "acceso a red.\n"
            "create_directory y run_pytest deben "
            "usar content con valor null.\n"
            "write_text_file debe incluir el "
            "contenido completo del archivo.\n"
            "Los step_number deben empezar en 1 "
            "y ser consecutivos.\n"
            "Todo el codigo debe poder "
            "importarse al ejecutar pytest "
            "desde la raiz del workspace.\n"
            "No utilices una estructura src "
            "salvo que crees un paquete Python "
            "completo y configures correctamente "
            "sus importaciones.\n"
            "Para proyectos sencillos, coloca "
            "los modulos importables en la raiz "
            "del workspace y las pruebas dentro "
            "de tests.\n"
            "Comprueba que cada import utilizado "
            "por las pruebas coincide exactamente "
            "con la ruta del modulo generado.\n"
            "La ultima accion debe ser "
            "run_pytest."
            "Ejemplo obligatorio: si una prueba "
            "usa 'from suma import sumar', debes "
            "crear suma.py con la funcion sumar, "
            "o crear suma/__init__.py que exporte "
            "la funcion desde el modulo interno.\n"
            "Crear solamente suma/suma.py no hace "
            "valido 'from suma import sumar'.\n"
        )

    def _build_prompt(
        self,
        plan: TaskPlan,
    ) -> str:
        plan_data = {
            "plan_id": plan.id,
            "task_id": plan.task_id,
            "version": plan.version,
            "objective": plan.objective,
            "scope": plan.scope,
            "technologies": (
                plan.technologies
            ),
            "interfaces": plan.interfaces,
            "inputs": plan.inputs,
            "outputs": plan.outputs,
            "data_entities": (
                plan.data_entities
            ),
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
        }

        serialized_plan = json.dumps(
            plan_data,
            ensure_ascii=False,
            indent=2,
        )

        return (
            "Genera el manifiesto de acciones "
            "para este plan aprobado.\n\n"
            f"{serialized_plan}"
        )

    def _build_correction_prompt(
        self,
        plan: TaskPlan,
        invalid_response: str,
        validation_error: str,
    ) -> str:
        response_summary = (
            invalid_response[
                -self
                ._MAX_RETRY_RESPONSE_CHARACTERS:
            ]
        )

        return (
            f"{self._build_prompt(plan)}\n\n"
            "Corrige la respuesta anterior y "
            "devuelve de nuevo el objeto JSON "
            "completo.\n"
            "No devuelvas solamente la accion "
            "corregida.\n"
            "Si una prueba importa una funcion "
            "desde un paquete, crea __init__.py "
            "y exporta expresamente esa funcion, "
            "o coloca la funcion en un modulo "
            "del mismo nombre en la raiz.\n"
            "La raiz del JSON corregido debe "
            "contener exactamente una unica "
            "propiedad: actions.\n"
            "No incluyas status, message, "
            "explanation, reasoning, summary "
            "ni ninguna otra propiedad.\n"
            "El formato obligatorio de la raiz "
            'es: {"actions": [...]}\n'
            "Error de validacion:\n"
            f"{validation_error}\n\n"
            "Respuesta anterior no valida:\n"
            f"{response_summary}"
        )

    def _parse_actions(
        self,
        response_text: str,
    ) -> tuple[ExecutionAction, ...]:
        json_text = self._extract_json(
            response_text
        )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as error:
            raise ExecutionActionGenerationError(
                "La respuesta no contiene un "
                "JSON valido"
            ) from error

        if not isinstance(data, dict):
            raise ExecutionActionGenerationError(
                "La respuesta debe ser un "
                "objeto JSON"
            )

        if set(data) != self._ROOT_KEYS:
            raise ExecutionActionGenerationError(
                "El objeto JSON debe contener "
                "solamente actions"
            )

        action_values = data["actions"]

        if not isinstance(
            action_values,
            list,
        ):
            raise ExecutionActionGenerationError(
                "actions debe ser una lista"
            )

        if not action_values:
            raise ExecutionActionGenerationError(
                "El manifiesto debe contener "
                "al menos una accion"
            )

        if (
            len(action_values)
            > self._limits.max_actions
        ):
            raise ExecutionActionGenerationError(
                "El manifiesto supera el numero "
                "maximo de acciones"
            )

        actions = tuple(
            self._parse_action(
                value=value,
                expected_step_number=index,
            )
            for index, value in enumerate(
                action_values,
                start=1,
            )
        )

        if not any(
            action.action_type
            == ExecutionActionType.RUN_PYTEST
            for action in actions
        ):
            raise ExecutionActionGenerationError(
                "El manifiesto debe ejecutar "
                "pruebas"
            )

        if (
            actions[-1].action_type
            != ExecutionActionType.RUN_PYTEST
        ):
            raise ExecutionActionGenerationError(
                "La ultima accion debe ser "
                "run_pytest"
            )
        self._validate_unique_write_paths(
            actions
        )

        self._validate_python_actions(
            actions
        )
        self._validate_python_actions(
            actions
        )

        return actions
    @staticmethod
    def _validate_unique_write_paths(
        actions: tuple[
            ExecutionAction,
            ...,
        ],
    ) -> None:
        written_paths: set[str] = set()

        for action in actions:
            if (
                action.action_type
                != ExecutionActionType
                .WRITE_TEXT_FILE
            ):
                continue

            normalized_path = (
                action.relative_path
                .replace("\\", "/")
            )

            if normalized_path in written_paths:
                raise (
                    ExecutionActionGenerationError(
                        "No se puede escribir mas "
                        "de una vez sobre la misma "
                        "ruta: "
                        f"{normalized_path}"
                    )
                )

            written_paths.add(normalized_path)

    def _validate_python_actions(
        self,
        actions: tuple[
            ExecutionAction,
            ...,
        ],
    ) -> None:
        python_files = {
            action.relative_path
            .replace("\\", "/")
            .lstrip("./")
            for action in actions
            if (
                action.action_type
                == ExecutionActionType
                .WRITE_TEXT_FILE
                and action.relative_path
                .lower()
                .endswith(".py")
            )
        }

        source_files = {
            path
            for path in python_files
            if not (
                path == "tests.py"
                or path.startswith("tests/")
                or path.startswith("test_")
            )
        }

        source_top_levels = {
            (
                path.split("/", maxsplit=1)[0]
                if "/" in path
                else path[:-3]
            )
            for path in source_files
        }

        for action in actions:
            if (
                action.action_type
                != ExecutionActionType
                .WRITE_TEXT_FILE
                or not action.relative_path
                .lower()
                .endswith(".py")
                or action.content is None
            ):
                continue

            relative_path = (
                action.relative_path
                .replace("\\", "/")
            )

            try:
                tree = ast.parse(
                    action.content,
                    filename=relative_path,
                )

            except SyntaxError as error:
                raise (
                    ExecutionActionGenerationError(
                        "El archivo generado "
                        f"'{relative_path}' contiene "
                        "sintaxis Python no valida: "
                        f"{error.msg}"
                    )
                ) from error

            if not (
                relative_path.startswith(
                    "tests/"
                )
                or relative_path.startswith(
                    "test_"
                )
            ):
                continue

            self._validate_test_imports(
                tree=tree,
                test_path=relative_path,
                python_files=python_files,
                source_top_levels=(
                    source_top_levels
                ),
            )

    def _validate_test_imports(
        self,
        tree: ast.AST,
        test_path: str,
        python_files: set[str],
        source_top_levels: set[str],
    ) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(
                    alias.name
                    for alias in node.names
                )

            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
            ):
                modules = (node.module,)

            else:
                continue

            for module in modules:
                top_level = module.split(
                    ".",
                    maxsplit=1,
                )[0]

                if (
                    top_level
                    not in source_top_levels
                ):
                    continue

                if self._module_exists(
                    module=module,
                    python_files=python_files,
                ):
                    continue

                if isinstance(
                    node,
                    ast.ImportFrom,
                ):
                    imported_modules_exist = all(
                        (
                            alias.name == "*"
                            or self._module_exists(
                                module=(
                                    f"{module}."
                                    f"{alias.name}"
                                ),
                                python_files=(
                                    python_files
                                ),
                            )
                        )
                        for alias in node.names
                    )

                    if imported_modules_exist:
                        continue

                raise (
                    ExecutionActionGenerationError(
                        "El modulo generado "
                        f"'{module}' no puede "
                        "importarse desde "
                        f"'{test_path}'. "
                        "Corrige la ruta del modulo, "
                        "crea __init__.py o corrige "
                        "el import de la prueba"
                    )
                )

    @staticmethod
    def _module_exists(
        module: str,
        python_files: set[str],
    ) -> bool:
        module_path = module.replace(
            ".",
            "/",
        )

        return (
            f"{module_path}.py"
            in python_files
            or (
                f"{module_path}/__init__.py"
                in python_files
            )
        )

    def _parse_action(
        self,
        value: Any,
        expected_step_number: int,
    ) -> ExecutionAction:
        if not isinstance(value, dict):
            raise ExecutionActionGenerationError(
                "Cada accion debe ser un "
                "objeto JSON"
            )

        keys = set(value)
        allowed_keys = (
            self._ACTION_REQUIRED_KEYS
            | self._ACTION_OPTIONAL_KEYS
        )

        if not self._ACTION_REQUIRED_KEYS.issubset(
            keys
        ):
            raise ExecutionActionGenerationError(
                "La accion no contiene todos "
                "los campos obligatorios"
            )

        if not keys.issubset(allowed_keys):
            raise ExecutionActionGenerationError(
                "La accion contiene campos no "
                "permitidos"
            )

        step_number = value["step_number"]

        if (
            not isinstance(step_number, int)
            or isinstance(step_number, bool)
            or step_number
            != expected_step_number
        ):
            raise ExecutionActionGenerationError(
                "Los step_number deben empezar "
                "en 1 y ser consecutivos"
            )

        name = value["name"]
        relative_path = value[
            "relative_path"
        ]
        action_type_value = value[
            "action_type"
        ]
        content = value.get("content")

        if not isinstance(name, str):
            raise ExecutionActionGenerationError(
                "name debe ser texto"
            )

        if not isinstance(
            relative_path,
            str,
        ):
            raise ExecutionActionGenerationError(
                "relative_path debe ser texto"
            )

        if not isinstance(
            action_type_value,
            str,
        ):
            raise ExecutionActionGenerationError(
                "action_type debe ser texto"
            )

        try:
            action_type = ExecutionActionType(
                action_type_value
            )
        except ValueError as error:
            raise ExecutionActionGenerationError(
                "El tipo de accion no esta "
                "permitido"
            ) from error
        if (
            action_type
            == ExecutionActionType
            .CREATE_DIRECTORY
            and not relative_path.strip()
        ):
            relative_path = "."

        self._validate_relative_path(
            relative_path
        )

        if (
            content is not None
            and not isinstance(content, str)
        ):
            raise ExecutionActionGenerationError(
                "content debe ser texto o null"
            )

        if (
            action_type
            == ExecutionActionType
            .WRITE_TEXT_FILE
            and content is not None
            and len(
                content.encode("utf-8")
            )
            > self._limits
            .max_text_file_bytes
        ):
            raise ExecutionActionGenerationError(
                "El contenido del archivo "
                "supera el limite permitido"
            )

        try:
            return ExecutionAction(
                step_number=step_number,
                name=name,
                action_type=action_type,
                relative_path=relative_path,
                content=content,
            )
        except ValueError as error:
            raise ExecutionActionGenerationError(
                str(error)
            ) from error

    @staticmethod
    def _validate_relative_path(
        relative_path: str,
    ) -> None:
        normalized = relative_path.strip()

        if not normalized:
            raise ExecutionActionGenerationError(
                "relative_path no puede estar "
                "vacio"
            )

        posix_path = PurePosixPath(
            normalized
        )
        windows_path = PureWindowsPath(
            normalized
        )

        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
        ):
            raise ExecutionActionGenerationError(
                "No se permiten rutas absolutas"
            )

        path_parts = (
            posix_path.parts
            + windows_path.parts
        )

        if ".." in path_parts:
            raise ExecutionActionGenerationError(
                "No se permiten rutas fuera "
                "del workspace"
            )

    @classmethod
    def _extract_json(
        cls,
        response_text: str,
    ) -> str:
        normalized = response_text.strip()

        if not normalized:
            raise ExecutionActionGenerationError(
                "La respuesta del modelo esta "
                "vacia"
            )

        match = cls._JSON_BLOCK_PATTERN.fullmatch(
            normalized
        )

        if match is not None:
            return match.group(1).strip()

        return normalized