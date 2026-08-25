from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlanStatus(str, Enum):
    DRAFT = "draft"
    PENDING_CLARIFICATION = (
        "pending_clarification"
    )
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class TaskPlan:
    id: int
    task_id: int
    version: int
    status: PlanStatus
    objective: str
    scope: tuple[str, ...]
    technologies: tuple[str, ...]
    interfaces: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    data_entities: tuple[str, ...]
    business_rules: tuple[str, ...]
    phases: tuple[str, ...]
    tests: tuple[str, ...]
    deployment: tuple[str, ...]
    pending_decisions: tuple[str, ...]
    excluded_items: tuple[str, ...]
    completion_criteria: tuple[str, ...]
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.task_id <= 0:
            raise ValueError(
                "task_id debe ser mayor que cero"
            )

        if self.version <= 0:
            raise ValueError(
                "version debe ser mayor que cero"
            )

        objective = self.objective.strip()

        if not objective:
            raise ValueError(
                "objective no puede estar vacío"
            )

        object.__setattr__(
            self,
            "objective",
            objective,
        )

        tuple_fields = (
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

        for field_name in tuple_fields:
            values = getattr(
                self,
                field_name,
            )

            normalized = tuple(
                value.strip()
                for value in values
                if value.strip()
            )

            object.__setattr__(
                self,
                field_name,
                normalized,
            )

    @property
    def requires_clarification(
        self,
    ) -> bool:
        return bool(self.pending_decisions)

    @property
    def can_be_approved(
        self,
    ) -> bool:
        return (
            not self.pending_decisions
            and bool(self.scope)
            and bool(self.technologies)
            and bool(self.phases)
            and bool(self.completion_criteria)
        )