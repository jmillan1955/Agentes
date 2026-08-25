from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from app.context.database import ContextDatabase
from app.planning.models import (
    PlanStatus,
    TaskPlan,
)


class TaskPlanRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def create(
        self,
        task_id: int,
        objective: str,
        scope: Iterable[str] = (),
        technologies: Iterable[str] = (),
        interfaces: Iterable[str] = (),
        inputs: Iterable[str] = (),
        outputs: Iterable[str] = (),
        data_entities: Iterable[str] = (),
        business_rules: Iterable[str] = (),
        phases: Iterable[str] = (),
        tests: Iterable[str] = (),
        deployment: Iterable[str] = (),
        pending_decisions: Iterable[str] = (),
        excluded_items: Iterable[str] = (),
        completion_criteria: Iterable[str] = (),
    ) -> TaskPlan:
        if task_id <= 0:
            raise ValueError(
                "task_id debe ser mayor que cero"
            )

        objective = objective.strip()

        if not objective:
            raise ValueError(
                "objective no puede estar vacío"
            )

        self._validate_task(task_id)

        values = {
            "scope": self._normalize(scope),
            "technologies": self._normalize(
                technologies
            ),
            "interfaces": self._normalize(
                interfaces
            ),
            "inputs": self._normalize(inputs),
            "outputs": self._normalize(outputs),
            "data_entities": self._normalize(
                data_entities
            ),
            "business_rules": self._normalize(
                business_rules
            ),
            "phases": self._normalize(phases),
            "tests": self._normalize(tests),
            "deployment": self._normalize(
                deployment
            ),
            "pending_decisions": self._normalize(
                pending_decisions
            ),
            "excluded_items": self._normalize(
                excluded_items
            ),
            "completion_criteria": self._normalize(
                completion_criteria
            ),
        }

        status = (
            PlanStatus.PENDING_CLARIFICATION
            if values["pending_decisions"]
            else PlanStatus.PENDING_APPROVAL
        )

        connection = self._database.connection

        version_row = connection.execute(
            """
            SELECT
                COALESCE(MAX(version), 0) + 1
                    AS next_version
            FROM task_plans
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        version = int(
            version_row["next_version"]
        )

        connection.execute(
            """
            UPDATE task_plans
            SET
                status = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            WHERE task_id = ?
              AND status IN (
                  'draft',
                  'pending_clarification',
                  'pending_approval'
              )
            """,
            (
                PlanStatus.SUPERSEDED.value,
                task_id,
            ),
        )

        cursor = connection.execute(
            """
            INSERT INTO task_plans (
                task_id,
                version,
                status,
                objective,
                scope_json,
                technologies_json,
                interfaces_json,
                inputs_json,
                outputs_json,
                data_entities_json,
                business_rules_json,
                phases_json,
                tests_json,
                deployment_json,
                pending_decisions_json,
                excluded_items_json,
                completion_criteria_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                task_id,
                version,
                status.value,
                objective,
                self._encode(values["scope"]),
                self._encode(
                    values["technologies"]
                ),
                self._encode(
                    values["interfaces"]
                ),
                self._encode(values["inputs"]),
                self._encode(values["outputs"]),
                self._encode(
                    values["data_entities"]
                ),
                self._encode(
                    values["business_rules"]
                ),
                self._encode(values["phases"]),
                self._encode(values["tests"]),
                self._encode(
                    values["deployment"]
                ),
                self._encode(
                    values["pending_decisions"]
                ),
                self._encode(
                    values["excluded_items"]
                ),
                self._encode(
                    values["completion_criteria"]
                ),
            ),
        )

        connection.commit()

        created = self.get_by_id(
            int(cursor.lastrowid)
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el plan creado"
            )

        return created

    def get_by_id(
        self,
        plan_id: int,
    ) -> TaskPlan | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                version,
                status,
                objective,
                scope_json,
                technologies_json,
                interfaces_json,
                inputs_json,
                outputs_json,
                data_entities_json,
                business_rules_json,
                phases_json,
                tests_json,
                deployment_json,
                pending_decisions_json,
                excluded_items_json,
                completion_criteria_json,
                created_at,
                updated_at
            FROM task_plans
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()

        return self._to_record(row)

    def get_latest(
        self,
        task_id: int,
    ) -> TaskPlan | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                version,
                status,
                objective,
                scope_json,
                technologies_json,
                interfaces_json,
                inputs_json,
                outputs_json,
                data_entities_json,
                business_rules_json,
                phases_json,
                tests_json,
                deployment_json,
                pending_decisions_json,
                excluded_items_json,
                completion_criteria_json,
                created_at,
                updated_at
            FROM task_plans
            WHERE task_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()

        return self._to_record(row)

    def list_by_task(
        self,
        task_id: int,
    ) -> list[TaskPlan]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                task_id,
                version,
                status,
                objective,
                scope_json,
                technologies_json,
                interfaces_json,
                inputs_json,
                outputs_json,
                data_entities_json,
                business_rules_json,
                phases_json,
                tests_json,
                deployment_json,
                pending_decisions_json,
                excluded_items_json,
                completion_criteria_json,
                created_at,
                updated_at
            FROM task_plans
            WHERE task_id = ?
            ORDER BY version
            """,
            (task_id,),
        ).fetchall()

        return [
            self._to_record_required(row)
            for row in rows
        ]

    def _validate_task(
        self,
        task_id: int,
    ) -> None:
        row = self._database.connection.execute(
            """
            SELECT id
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"No existe la tarea #{task_id}"
            )

    @staticmethod
    def _normalize(
        values: Iterable[str],
    ) -> tuple[str, ...]:
        return tuple(
            value.strip()
            for value in values
            if value.strip()
        )

    @staticmethod
    def _encode(
        values: tuple[str, ...],
    ) -> str:
        return json.dumps(
            values,
            ensure_ascii=False,
        )

    @staticmethod
    def _decode(
        value: str,
        field_name: str,
    ) -> tuple[str, ...]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"{field_name} contiene "
                "un JSON no válido"
            ) from error

        if not isinstance(decoded, list):
            raise RuntimeError(
                f"{field_name} debe contener "
                "una lista JSON"
            )

        if not all(
            isinstance(item, str)
            for item in decoded
        ):
            raise RuntimeError(
                f"{field_name} debe contener "
                "solamente textos"
            )

        return tuple(decoded)

    @staticmethod
    def _to_record(
        row: sqlite3.Row | None,
    ) -> TaskPlan | None:
        if row is None:
            return None

        return (
            TaskPlanRepository
            ._to_record_required(row)
        )

    @staticmethod
    def _to_record_required(
        row: sqlite3.Row,
    ) -> TaskPlan:
        try:
            status = PlanStatus(
                row["status"]
            )
        except ValueError as error:
            raise RuntimeError(
                "El plan contiene un "
                "estado desconocido"
            ) from error

        return TaskPlan(
            id=row["id"],
            task_id=row["task_id"],
            version=row["version"],
            status=status,
            objective=row["objective"],
            scope=TaskPlanRepository._decode(
                row["scope_json"],
                "scope_json",
            ),
            technologies=(
                TaskPlanRepository._decode(
                    row["technologies_json"],
                    "technologies_json",
                )
            ),
            interfaces=(
                TaskPlanRepository._decode(
                    row["interfaces_json"],
                    "interfaces_json",
                )
            ),
            inputs=TaskPlanRepository._decode(
                row["inputs_json"],
                "inputs_json",
            ),
            outputs=TaskPlanRepository._decode(
                row["outputs_json"],
                "outputs_json",
            ),
            data_entities=(
                TaskPlanRepository._decode(
                    row["data_entities_json"],
                    "data_entities_json",
                )
            ),
            business_rules=(
                TaskPlanRepository._decode(
                    row["business_rules_json"],
                    "business_rules_json",
                )
            ),
            phases=TaskPlanRepository._decode(
                row["phases_json"],
                "phases_json",
            ),
            tests=TaskPlanRepository._decode(
                row["tests_json"],
                "tests_json",
            ),
            deployment=(
                TaskPlanRepository._decode(
                    row["deployment_json"],
                    "deployment_json",
                )
            ),
            pending_decisions=(
                TaskPlanRepository._decode(
                    row[
                        "pending_decisions_json"
                    ],
                    "pending_decisions_json",
                )
            ),
            excluded_items=(
                TaskPlanRepository._decode(
                    row["excluded_items_json"],
                    "excluded_items_json",
                )
            ),
            completion_criteria=(
                TaskPlanRepository._decode(
                    row[
                        "completion_criteria_json"
                    ],
                    "completion_criteria_json",
                )
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )