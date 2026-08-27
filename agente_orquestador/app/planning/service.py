from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
import re
import unicodedata
from app.tasks import (
    TaskClarificationResponse,
)
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

        plan_data["pending_decisions"] = (
            self._remove_answered_decisions(
                pending_decisions=(
                    plan_data[
                        "pending_decisions"
                    ]
                ),
                clarification_responses=(
                    responses
                ),
            )
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
    def _remove_answered_decisions(
        cls,
        pending_decisions: tuple[
            str,
            ...,
        ],
        clarification_responses: tuple[
            TaskClarificationResponse,
            ...,
        ],
    ) -> tuple[str, ...]:
        answered_questions = tuple(
            question
            for response
            in clarification_responses
            for question in response.questions
        )

        return tuple(
            decision
            for decision in pending_decisions
            if not any(
                cls._describes_same_decision(
                    first=decision,
                    second=question,
                )
                for question
                in answered_questions
            )
        )

    @classmethod
    def _describes_same_decision(
        cls,
        first: str,
        second: str,
    ) -> bool:
        normalized_first = (
            cls._normalize_decision_text(
                first
            )
        )
        normalized_second = (
            cls._normalize_decision_text(
                second
            )
        )

        if (
            normalized_first
            in normalized_second
            or normalized_second
            in normalized_first
        ):
            return True

        first_terms = cls._meaningful_terms(
            normalized_first
        )
        second_terms = cls._meaningful_terms(
            normalized_second
        )

        if not first_terms or not second_terms:
            return False

        shared_terms = (
            first_terms & second_terms
        )

        smallest_size = min(
            len(first_terms),
            len(second_terms),
        )

        return (
            len(shared_terms) >= 2
            and (
                len(shared_terms)
                / smallest_size
            )
            >= 0.6
        )

    @staticmethod
    def _normalize_decision_text(
        text: str,
    ) -> str:
        normalized = unicodedata.normalize(
            "NFKD",
            text,
        )

        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        return " ".join(
            re.findall(
                r"[a-z0-9]+",
                without_accents.lower(),
            )
        )

    @staticmethod
    def _meaningful_terms(
        normalized_text: str,
    ) -> set[str]:
        ignored_terms = {
            "a",
            "al",
            "como",
            "con",
            "de",
            "del",
            "el",
            "en",
            "la",
            "las",
            "los",
            "o",
            "para",
            "por",
            "que",
            "se",
            "un",
            "una",
            "y",
        }

        return {
            term
            for term in normalized_text.split()
            if (
                len(term) > 1
                and term not in ignored_terms
            )
        }

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