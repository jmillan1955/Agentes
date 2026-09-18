from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agente_ia.conversation_store import ConversationStore
from agente_ia.task_workflow import (
    ApprovalError,
    ExecutionBlockedError,
    PlanGenerationError,
    StructuredPlanGenerator,
    TaskWorkflowService,
    TaskWorkflowStore,
)


def valid_plan_json(objective: str = "Implementar el cambio") -> str:
    return json.dumps(
        {
            "objective": objective,
            "professional_prompt": "Implementa el cambio solicitado sin ampliar el alcance.",
            "scope": ["Codigo del componente afectado"],
            "technologies": ["Python", "SQLite"],
            "phases": [
                {
                    "name": "Implementacion",
                    "objective": "Aplicar el cambio de forma aislada",
                    "deliverables": ["Codigo", "Pruebas"],
                }
            ],
            "tests": ["Pruebas unitarias", "Suite completa"],
            "risks": ["Regresion de comportamiento existente"],
            "exclusions": ["Despliegue a produccion"],
            "completion_criteria": ["Todas las pruebas pasan"],
        },
        ensure_ascii=False,
    )


class FakeProvider:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("El proveedor recibio mas llamadas de las esperadas")
        return self.responses.pop(0)


class TaskWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary.name) / "conversations.db"
        conversation_store = ConversationStore(database_path)
        conversation_store.initialize()
        user_id = conversation_store.get_or_create_user(
            77, username="tester", first_name="Test", last_name=None
        )
        self.conversation = conversation_store.get_or_create_active_conversation(user_id, 900)
        self.store = TaskWorkflowStore(database_path)
        self.store.initialize()
        self.service = TaskWorkflowService(self.store)
        self.database_path = database_path

    def tearDown(self) -> None:
        self.temporary.cleanup()

    async def submit_clear_task(self, source_key: str = "telegram:900:1"):
        provider = FakeProvider(valid_plan_json())
        outcome = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key=source_key,
            request_text="Implementa validacion de entrada en AgenteIA-local con Python",
            provider=provider,
        )
        return outcome, provider

    async def test_invalid_model_output_is_repaired_and_retried(self) -> None:
        provider = FakeProvider("esto no es JSON", valid_plan_json())

        outcome = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key="telegram:900:10",
            request_text="Implementa validacion de entrada en AgenteIA-local con Python",
            provider=provider,
        )

        self.assertIsNotNone(outcome.plan)
        self.assertEqual(len(provider.prompts), 2)
        self.assertIn("no cumple el contrato", provider.prompts[1])

    async def test_invalid_output_fails_after_bounded_retries(self) -> None:
        provider = FakeProvider("mal", "tambien mal", "sigue mal")

        with self.assertRaises(PlanGenerationError):
            await self.service.submit(
                conversation_id=self.conversation.id,
                source_key="telegram:900:11",
                request_text="Implementa validacion de entrada en AgenteIA-local con Python",
                provider=provider,
            )

        self.assertEqual(len(provider.prompts), 3)

    async def test_duplicate_message_does_not_duplicate_task_or_plan(self) -> None:
        first_provider = FakeProvider(valid_plan_json())
        second_provider = FakeProvider()
        arguments = {
            "conversation_id": self.conversation.id,
            "source_key": "telegram:900:20",
            "request_text": "Implementa validacion de entrada en AgenteIA-local con Python",
        }

        first = await self.service.submit(provider=first_provider, **arguments)
        second = await self.service.submit(provider=second_provider, **arguments)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.task.id, second.task.id)
        self.assertEqual(first.plan.id, second.plan.id)
        self.assertEqual(second_provider.prompts, [])
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_requests").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_plans").fetchone()[0], 1)
        finally:
            connection.close()

    async def test_material_clarification_precedes_plan(self) -> None:
        provider = FakeProvider()

        outcome = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key="telegram:900:30",
            request_text="Crea una app de inventario",
            provider=provider,
        )

        self.assertIsNone(outcome.plan)
        self.assertEqual(len(outcome.questions), 2)
        self.assertEqual(provider.prompts, [])

        clarification_provider = FakeProvider(valid_plan_json("Crear la app de inventario"))
        clarified = await self.service.clarify(
            outcome.task.id,
            conversation_id=self.conversation.id,
            source_key="telegram:900:31",
            answer="En AgenteIA-local, con Python y SQLite",
            provider=clarification_provider,
        )

        self.assertIsNotNone(clarified.plan)
        self.assertIn("En AgenteIA-local", clarification_provider.prompts[0])

    async def test_incomplete_clarification_keeps_task_pending(self) -> None:
        outcome = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key="telegram:900:32",
            request_text="Crea una app de inventario",
            provider=FakeProvider(),
        )

        clarified = await self.service.clarify(
            outcome.task.id,
            conversation_id=self.conversation.id,
            source_key="telegram:900:33",
            answer="En AgenteIA-local",
            provider=FakeProvider(),
        )

        self.assertIsNone(clarified.plan)
        self.assertEqual(clarified.questions, ("¿Qué plataforma o tecnología debe usarse?",))

    async def test_duplicate_clarification_does_not_create_another_version(self) -> None:
        outcome = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key="telegram:900:34",
            request_text="Crea una app de inventario",
            provider=FakeProvider(),
        )
        arguments = {
            "task_id": outcome.task.id,
            "conversation_id": self.conversation.id,
            "source_key": "telegram:900:35",
            "answer": "En AgenteIA-local, con Python y SQLite",
        }

        first = await self.service.clarify(
            provider=FakeProvider(valid_plan_json("Crear inventario")), **arguments
        )
        duplicate_provider = FakeProvider()
        second = await self.service.clarify(provider=duplicate_provider, **arguments)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.plan.id, second.plan.id)
        self.assertEqual(duplicate_provider.prompts, [])

    async def test_new_plan_supersedes_old_and_only_latest_can_be_approved(self) -> None:
        first, _ = await self.submit_clear_task("telegram:900:40")
        second_provider = FakeProvider(valid_plan_json("Objetivo revisado"))

        revised = await self.service.clarify(
            first.task.id,
            conversation_id=self.conversation.id,
            source_key="telegram:900:41",
            answer="Incluye tambien una prueba de integracion",
            provider=second_provider,
        )

        self.assertEqual(first.plan.version, 1)
        self.assertEqual(revised.plan.version, 2)
        with self.assertRaises(ApprovalError):
            self.service.approve(
                first.task.id,
                conversation_id=self.conversation.id,
                version=first.plan.version,
                plan_hash=first.plan.plan_hash,
                approved_by=77,
                source_key="telegram:900:42",
            )

        approval = self.service.approve(
            first.task.id,
            conversation_id=self.conversation.id,
            version=revised.plan.version,
            plan_hash=revised.plan.plan_hash,
            approved_by=77,
            source_key="telegram:900:43",
        )
        self.assertEqual(approval.plan_version, 2)

    async def test_execution_is_absolutely_blocked_before_approval(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:50")
        calls: list[int] = []

        async def executor(plan) -> None:
            calls.append(plan.id)

        with self.assertRaises(ExecutionBlockedError):
            await self.service.execute(
                outcome.task.id,
                conversation_id=self.conversation.id,
                version=outcome.plan.version,
                plan_hash=outcome.plan.plan_hash,
                requested_by=77,
                source_key="telegram:900:51",
                executor=executor,
            )

        self.assertEqual(calls, [])
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 0)
        finally:
            connection.close()

    async def test_approved_execution_is_idempotent(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:60")
        self.service.approve(
            outcome.task.id,
            conversation_id=self.conversation.id,
            version=outcome.plan.version,
            plan_hash=outcome.plan.plan_hash,
            approved_by=77,
            source_key="telegram:900:61",
        )
        calls: list[int] = []

        async def executor(plan) -> None:
            calls.append(plan.id)

        arguments = {
            "task_id": outcome.task.id,
            "conversation_id": self.conversation.id,
            "version": outcome.plan.version,
            "plan_hash": outcome.plan.plan_hash,
            "requested_by": 77,
            "source_key": "telegram:900:62",
            "executor": executor,
        }
        first = await self.service.execute(**arguments)
        second = await self.service.execute(**arguments)

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.state, "completed")
        self.assertEqual(calls, [outcome.plan.id])
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 1)
        finally:
            connection.close()

    async def test_approval_is_idempotent_for_same_source(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:70")
        arguments = {
            "task_id": outcome.task.id,
            "conversation_id": self.conversation.id,
            "version": outcome.plan.version,
            "plan_hash": outcome.plan.plan_hash,
            "approved_by": 77,
            "source_key": "telegram:900:71",
        }

        first = self.service.approve(**arguments)
        second = self.service.approve(**arguments)

        self.assertEqual(first.id, second.id)
        with self.assertRaisesRegex(ApprovalError, "esta conversacion"):
            self.service.approve(**{**arguments, "conversation_id": self.conversation.id + 1})

        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_approvals").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 0)
        finally:
            connection.close()

    async def test_approval_rejects_reused_source_with_different_data(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:72")
        arguments = {
            "task_id": outcome.task.id,
            "conversation_id": self.conversation.id,
            "version": outcome.plan.version,
            "plan_hash": outcome.plan.plan_hash,
            "approved_by": 77,
            "source_key": "telegram:900:73",
        }
        self.service.approve(**arguments)

        with self.assertRaisesRegex(ApprovalError, "clave idempotente"):
            self.service.approve(**{**arguments, "approved_by": 78})
        with self.assertRaisesRegex(ApprovalError, "pendiente"):
            self.service.approve(**{**arguments, "source_key": "telegram:900:74"})

        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_approvals").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 0)
        finally:
            connection.close()

    async def test_approval_rejects_task_from_another_conversation_and_unknown_task(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:75")
        base = {
            "task_id": outcome.task.id,
            "version": outcome.plan.version,
            "plan_hash": outcome.plan.plan_hash,
            "approved_by": 77,
        }

        with self.assertRaisesRegex(ApprovalError, "esta conversacion"):
            self.service.approve(
                **base,
                conversation_id=self.conversation.id + 1,
                source_key="telegram:901:76",
            )
        with self.assertRaisesRegex(ApprovalError, "esta conversacion"):
            self.service.approve(
                **{**base, "task_id": 9_999},
                conversation_id=self.conversation.id,
                source_key="telegram:900:77",
            )

    async def test_approval_rejects_task_without_plan(self) -> None:
        pending = await self.service.submit(
            conversation_id=self.conversation.id,
            source_key="telegram:900:78",
            request_text="Crea una app de inventario",
            provider=FakeProvider(),
        )

        with self.assertRaisesRegex(ApprovalError, "aun no tiene un plan"):
            self.service.approve(
                pending.task.id,
                conversation_id=self.conversation.id,
                version=1,
                plan_hash="a" * 64,
                approved_by=77,
                source_key="telegram:900:79",
            )

    async def test_approval_rejects_future_version_wrong_hash_and_invalid_plan_states(self) -> None:
        outcome, _ = await self.submit_clear_task("telegram:900:80")
        base = {
            "task_id": outcome.task.id,
            "conversation_id": self.conversation.id,
            "approved_by": 77,
        }
        with self.assertRaisesRegex(ApprovalError, "ultima version exacta"):
            self.service.approve(
                **base,
                version=outcome.plan.version + 1,
                plan_hash=outcome.plan.plan_hash,
                source_key="telegram:900:81",
            )
        with self.assertRaisesRegex(ApprovalError, "ultima version exacta"):
            self.service.approve(
                **base,
                version=outcome.plan.version,
                plan_hash="b" * 64,
                source_key="telegram:900:82",
            )

        for index, state in enumerate(("superseded", "planning_failed"), start=83):
            with self.subTest(state=state):
                connection = sqlite3.connect(self.database_path)
                try:
                    connection.execute(
                        "UPDATE task_plans SET status = ? WHERE id = ?",
                        (state, outcome.plan.id),
                    )
                    connection.commit()
                finally:
                    connection.close()
                with self.assertRaisesRegex(ApprovalError, "pendiente"):
                    self.service.approve(
                        **base,
                        version=outcome.plan.version,
                        plan_hash=outcome.plan.plan_hash,
                        source_key=f"telegram:900:{index}",
                    )

    def test_approval_service_validates_types_ranges_hash_and_source(self) -> None:
        valid = {
            "task_id": 1,
            "conversation_id": self.conversation.id,
            "version": 1,
            "plan_hash": "a" * 64,
            "approved_by": 77,
            "source_key": "telegram:900:90",
        }
        invalid = [
            {"task_id": True},
            {"task_id": 0},
            {"task_id": 9_223_372_036_854_775_808},
            {"version": -1},
            {"plan_hash": "A" * 64},
            {"plan_hash": "a" * 63},
            {"source_key": " "},
        ]
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(ApprovalError):
                self.service.approve(**{**valid, **override})

    def test_parser_accepts_json_surrounded_by_small_model_preamble(self) -> None:
        generator = StructuredPlanGenerator()

        plan = generator.parse_and_validate("Resultado:\n" + valid_plan_json())

        self.assertEqual(plan.objective, "Implementar el cambio")


if __name__ == "__main__":
    unittest.main()
