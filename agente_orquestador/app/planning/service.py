from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.context.task_clarification_response_repository import (
    TaskClarificationResponseRepository,
)
from app.context.task_plan_repository import (
    TaskPlanRepository,
)
from app.context.task_repository import (
    TaskRepository,
)
from app.planning.models import TaskPlan
from app.planning.prompt_builder import (
    PlanningPromptBuilder,
)
from app.providers import LanguageProvider


class PlanningGenerationError(Exception):
    """Error al generar una planificación."""


@dataclass(frozen=True, slots=True)
class GeneratedPlan:
    plan: TaskPlan
    model: str
    elapsed_seconds: float


class PlanningService:
    _LIST_FIELDS = (
        "scope",
        "technologies",
        "interfaces",
        "inputs",
        "outputs",
        "data_entities",
        "business_rules",
        "phases",
        "tests",
        "deployment",
        "pending_decisions",
        "excluded_items",
        "completion_criteria",
    )

    def __init__(
        self,
        task_repository: TaskRepository,
        clarification_repository: (
            TaskClarificationResponseRepository
        ),
        plan_repository: TaskPlanRepository,
        prompt_builder: PlanningPromptBuilder,
        language_provider: LanguageProvider,
    ) -> None:
        self._task_repository = task_repository
        self._clarification_repository = (
            clarification_repository
        )
        self._plan_repository = plan_repository
        self._prompt_builder = prompt_builder
        self._language_provider = (
            language_provider
        )

    def generate(
        self,
        task_id: int,
    ) -> GeneratedPlan:
        task = self._task_repository.get_by_id(
            task_id
        )

        if task is None:
            raise ValueError(
                f"No existe la tarea #{task_id}"
            )

        responses = (
            self._clarification_repository
            .list_by_task(task_id)
        )

        prompt = self._prompt_builder.build(
            task=task,
            clarification_responses=responses,
        )

        language_response = (
            self._language_provider.generate(
                prompt=prompt.user_prompt,
                system_prompt=(
                    prompt.system_prompt
                ),
            )
        )

        plan_data = self._parse_response(
            language_response.text
        )

        plan = self._plan_repository.create(
            task_id=task.id,
            objective=plan_data["objective"],
            scope=plan_data["scope"],
            technologies=(
                plan_data["technologies"]
            ),
            interfaces=plan_data["interfaces"],
            inputs=plan_data["inputs"],
            outputs=plan_data["outputs"],
            data_entities=(
                plan_data["data_entities"]
            ),
            business_rules=(
                plan_data["business_rules"]
            ),
            phases=plan_data["phases"],
            tests=plan_data["tests"],
            deployment=plan_data["deployment"],
            pending_decisions=(
                plan_data["pending_decisions"]
            ),
            excluded_items=(
                plan_data["excluded_items"]
            ),
            completion_criteria=(
                plan_data[
                    "completion_criteria"
                ]
            ),
        )

        return GeneratedPlan(
            plan=plan,
            model=language_response.model,
            elapsed_seconds=(
                language_response.elapsed_seconds
            ),
        )

    @classmethod
    def _parse_response(
        cls,
        text: str,
    ) -> dict[str, Any]:
        json_text = cls._extract_json(text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as error:
            raise PlanningGenerationError(
                "La planificación no contiene "
                "un JSON válido"
            ) from error

        if not isinstance(data, dict):
            raise PlanningGenerationError(
                "La planificación debe ser "
                "un objeto JSON"
            )

        objective = data.get("objective")

        if (
            not isinstance(objective, str)
            or not objective.strip()
        ):
            raise PlanningGenerationError(
                "La planificación no contiene "
                "un objetivo válido"
            )

        normalized: dict[str, Any] = {
            "objective": objective.strip(),
        }

        for field_name in cls._LIST_FIELDS:
            value = data.get(field_name)

            if not isinstance(value, list):
                raise PlanningGenerationError(
                    "El campo "
                    f"'{field_name}' debe ser "
                    "una lista JSON"
                )

            if not all(
                isinstance(item, str)
                for item in value
            ):
                raise PlanningGenerationError(
                    "El campo "
                    f"'{field_name}' debe contener "
                    "solamente textos"
                )

            normalized[field_name] = tuple(
                item.strip()
                for item in value
                if item.strip()
            )

        return normalized

    @staticmethod
    def _extract_json(
        text: str,
    ) -> str:
        clean_text = text.strip()

        if not clean_text:
            raise PlanningGenerationError(
                "El proveedor ha devuelto una "
                "planificación vacía"
            )

        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")

        if (
            first_brace == -1
            or last_brace == -1
            or last_brace < first_brace
        ):
            raise PlanningGenerationError(
                "La planificación no contiene "
                "un objeto JSON"
            )

        return clean_text[
            first_brace:last_brace + 1
        ]