from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agente_ia import ConversationStore, ModelResponse
from agente_telegram.bot import TelegramAgent, parse_approval_identifier


def plan_response() -> str:
    return json.dumps(
        {
            "objective": "Agregar validacion",
            "professional_prompt": "Implementa la validacion y conserva el comportamiento existente.",
            "scope": ["Entrada del bot"],
            "technologies": ["Python"],
            "phases": [
                {
                    "name": "Cambio",
                    "objective": "Validar la entrada",
                    "deliverables": ["Codigo", "Pruebas"],
                }
            ],
            "tests": ["Caso valido", "Caso invalido"],
            "risks": ["Falso positivo"],
            "exclusions": ["Despliegue"],
            "completion_criteria": ["Suite verde"],
        }
    )


class FakeModelService:
    model = "gpt-5.6-sol"
    reasoning_effort = "high"
    account_plan = "plus"

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str]] = []

    async def ask(self, chat_id: int, prompt: str, *, initial_context: str = "") -> ModelResponse:
        self.calls.append((chat_id, prompt, initial_context))
        is_plan = "Actua como arquitecto de software" in prompt
        return ModelResponse(
            text=plan_response() if is_plan else "Respuesta conceptual",
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            elapsed_seconds=0.01,
            input_tokens=10,
            output_tokens=20,
            cached_input_tokens=0,
            reasoning_output_tokens=0,
            account_plan=self.account_plan,
        )


class NoMapService:
    @staticmethod
    def supports(prompt: str) -> bool:
        del prompt
        return False


class TaskTelegramIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary.name) / "conversation.db"
        store = ConversationStore(database_path)
        store.initialize()
        self.model = FakeModelService()
        self.agent = TelegramAgent(
            SimpleNamespace(allowed_user_ids=(77,), task_approver_user_ids=(77,)),
            {"sol": self.model},
            "sol",
            SimpleNamespace(),
            NoMapService(),
            SimpleNamespace(),
            SimpleNamespace(),
            store,
        )
        self.agent.task_workflow.store.initialize()
        self.agent.responder_telegram = AsyncMock()
        self.database_path = database_path

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_approval_identifier_accepts_only_ascii_sqlite_boundaries(self) -> None:
        self.assertEqual(parse_approval_identifier("1"), 1)
        self.assertEqual(
            parse_approval_identifier("9223372036854775807"),
            9_223_372_036_854_775_807,
        )
        self.assertIsNone(parse_approval_identifier("0"))
        self.assertIsNone(parse_approval_identifier("9223372036854775808"))
        self.assertIsNone(parse_approval_identifier("1" * 5_000))
        self.assertIsNone(parse_approval_identifier("١"))

    @staticmethod
    def make_update(message_id: int, *, user_id: int = 77, chat_id: int = 900) -> SimpleNamespace:
        return SimpleNamespace(
            effective_user=SimpleNamespace(
                id=user_id, username="tester", first_name="Test", last_name=None
            ),
            effective_chat=SimpleNamespace(id=chat_id),
            message=SimpleNamespace(message_id=message_id),
        )

    @staticmethod
    def make_context() -> SimpleNamespace:
        return SimpleNamespace(user_data={}, chat_data={}, args=[])

    async def test_direct_task_generates_plan_but_never_execution(self) -> None:
        completed = await self.agent.procesar_prompt(
            self.make_update(1),
            self.make_context(),
            "Implementa validacion de entrada en AgenteIA-local con Python",
        )

        self.assertTrue(completed)
        self.assertEqual(len(self.model.calls), 1)
        self.assertIn("Actua como arquitecto de software", self.model.calls[0][1])
        response_text = self.agent.responder_telegram.await_args.args[1]
        self.assertIn("Plan de tarea #", response_text)
        self.assertIn("/aprobar_tarea", response_text)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_requests").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_plans").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 0)
        finally:
            connection.close()

    async def test_conceptual_query_keeps_normal_model_path(self) -> None:
        completed = await self.agent.procesar_prompt(
            self.make_update(2),
            self.make_context(),
            "Explicame como implementar validacion de entrada",
        )

        self.assertTrue(completed)
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(self.model.calls[0][1], "Explicame como implementar validacion de entrada")
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_requests").fetchone()[0], 0)
        finally:
            connection.close()

    async def create_pending_plan(self):
        await self.agent.procesar_prompt(
            self.make_update(10),
            self.make_context(),
            "Implementa validacion de entrada en AgenteIA-local con Python",
        )
        task = self.agent.task_workflow.store.latest_task(
            self.agent.conversacion_activa(self.make_update(11)).id
        )
        self.assertIsNotNone(task)
        plan = self.agent.task_workflow.store.latest_plan(task.id)
        self.assertIsNotNone(plan)
        self.agent.responder_telegram.reset_mock()
        return task, plan

    async def test_approval_command_records_only_the_exact_approved_plan(self) -> None:
        task, plan = await self.create_pending_plan()
        context = self.make_context()
        context.args = [str(task.id), str(plan.version), plan.plan_hash]

        await self.agent.aprobar_tarea(self.make_update(12), context)

        response = self.agent.responder_telegram.await_args.args[1]
        self.assertIn("Plan aprobado", response)
        self.assertIn("no se ha ejecutado nada", response)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_approvals").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0], 0)
        finally:
            connection.close()

    async def test_authorization_and_approver_permission_precede_task_lookup(self) -> None:
        original = self.agent.task_workflow.approve
        self.agent.task_workflow.approve = Mock(side_effect=AssertionError("no debe consultarse"))
        try:
            context = self.make_context()
            context.args = ["1", "1", "a" * 64]

            await self.agent.aprobar_tarea(self.make_update(20, user_id=88), context)
            self.agent.task_workflow.approve.assert_not_called()
            self.agent.responder_telegram.assert_not_awaited()

            self.agent.settings.task_approver_user_ids = ()
            await self.agent.aprobar_tarea(self.make_update(21), context)
            self.agent.task_workflow.approve.assert_not_called()
            self.assertIn("no tiene permiso", self.agent.responder_telegram.await_args.args[1])
        finally:
            self.agent.task_workflow.approve = original

    async def test_incomplete_updates_are_rejected_without_lookup(self) -> None:
        original = self.agent.task_workflow.approve
        self.agent.task_workflow.approve = Mock()
        context = self.make_context()
        context.args = ["1", "1", "a" * 64]
        updates = [
            SimpleNamespace(effective_user=None, effective_chat=SimpleNamespace(id=900), message=SimpleNamespace(message_id=1)),
            SimpleNamespace(effective_user=SimpleNamespace(id=77), effective_chat=None, message=SimpleNamespace(message_id=1)),
            SimpleNamespace(effective_user=SimpleNamespace(id=77), effective_chat=SimpleNamespace(id=900), message=None),
            SimpleNamespace(effective_user=SimpleNamespace(id=77), effective_chat=SimpleNamespace(id=900), message=SimpleNamespace(message_id=0)),
            SimpleNamespace(effective_user=SimpleNamespace(id=True), effective_chat=SimpleNamespace(id=900), message=SimpleNamespace(message_id=1)),
        ]
        try:
            for update in updates:
                with self.subTest(update=update):
                    await self.agent.aprobar_tarea(update, context)
            self.agent.task_workflow.approve.assert_not_called()
        finally:
            self.agent.task_workflow.approve = original

    async def test_approval_command_rejects_invalid_syntax_ranges_and_hashes(self) -> None:
        original = self.agent.task_workflow.approve
        self.agent.task_workflow.approve = Mock()
        invalid_arguments = [
            [],
            ["1", "1"],
            ["1", "1", "a" * 64, "extra"],
            ["0", "1", "a" * 64],
            ["-1", "1", "a" * 64],
            ["١", "1", "a" * 64],
            ["9223372036854775808", "1", "a" * 64],
            ["1", "0", "a" * 64],
            ["1", "1", "A" * 64],
            ["1", "1", "a" * 63],
        ]
        try:
            for message_id, args in enumerate(invalid_arguments, start=30):
                context = self.make_context()
                context.args = args
                with self.subTest(args=args):
                    await self.agent.aprobar_tarea(self.make_update(message_id), context)
            self.agent.task_workflow.approve.assert_not_called()
        finally:
            self.agent.task_workflow.approve = original

    async def test_internal_database_error_is_not_exposed(self) -> None:
        original = self.agent.task_workflow.approve
        self.agent.task_workflow.approve = Mock(
            side_effect=sqlite3.OperationalError("SECRET sqlite table task_approvals")
        )
        context = self.make_context()
        context.args = ["1", "1", "a" * 64]
        try:
            await self.agent.aprobar_tarea(self.make_update(50), context)
        finally:
            self.agent.task_workflow.approve = original

        response = self.agent.responder_telegram.await_args.args[1]
        self.assertIn("error interno", response)
        self.assertNotIn("SECRET", response)
        self.assertNotIn("sqlite", response.lower())


if __name__ == "__main__":
    unittest.main()
