from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agente_ia.codex_luna import CodexModelService, calculate_api_cost_usd


class FakeCodex:
    def __init__(self) -> None:
        self.account = AsyncMock(
            return_value=SimpleNamespace(
                account=SimpleNamespace(
                    root=SimpleNamespace(
                        type="chatgpt",
                        plan_type=SimpleNamespace(value="free"),
                    )
                )
            )
        )
        effort = SimpleNamespace(reasoning_effort=SimpleNamespace(value="low"))
        model = SimpleNamespace(
            model="gpt-5.6-terra",
            supported_reasoning_efforts=[effort],
        )
        self.models = AsyncMock(return_value=SimpleNamespace(data=[model]))
        self.thread = SimpleNamespace(
            run=AsyncMock(
                return_value=SimpleNamespace(
                    final_response="Respuesta de Terra",
                    duration_ms=1250,
                    usage=SimpleNamespace(
                        last=SimpleNamespace(
                            input_tokens=10,
                            output_tokens=5,
                            cached_input_tokens=2,
                            reasoning_output_tokens=1,
                        )
                    ),
                )
            )
        )
        self.thread_start = AsyncMock(return_value=self.thread)
        self.close = AsyncMock()

    async def __aenter__(self):
        return self


class CodexModelServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.fake = FakeCodex()
        self.service = CodexModelService(
            Path.cwd(), codex_factory=Mock(return_value=self.fake)
        )
        await self.service.start()

    async def asyncTearDown(self) -> None:
        await self.service.close()

    async def test_reuses_conversation_for_same_chat(self) -> None:
        first = await self.service.ask(123, "Primera pregunta")
        second = await self.service.ask(123, "Segunda pregunta")

        self.assertEqual(first.text, "Respuesta de Terra")
        self.assertEqual(second.reasoning_effort, "none")
        self.fake.thread_start.assert_awaited_once()
        self.assertEqual(self.fake.thread.run.await_count, 2)

    async def test_new_conversation_creates_another_thread(self) -> None:
        await self.service.ask(123, "Primera pregunta")
        await self.service.new_conversation(123)
        await self.service.ask(123, "Pregunta sin contexto")

        self.assertEqual(self.fake.thread_start.await_count, 2)

    async def test_passes_prompt_without_modifying_it(self) -> None:
        await self.service.ask(123, "Texto literal")

        args = self.fake.thread.run.await_args
        self.assertEqual(args.args[0], "Texto literal")
        self.assertEqual(args.kwargs["effort"], "none")
        self.assertEqual(
            self.fake.thread_start.await_args.kwargs["model"],
            "gpt-5.6-terra",
        )

    async def test_restores_context_only_when_creating_thread(self) -> None:
        await self.service.ask(
            123,
            "¿Qué te dije?",
            initial_context="Usuario: Mi color favorito es verde.",
        )
        first_prompt = self.fake.thread.run.await_args.args[0]
        await self.service.ask(
            123,
            "¿Y ahora?",
            initial_context="Este texto no debe repetirse.",
        )
        second_prompt = self.fake.thread.run.await_args.args[0]

        self.assertIn("Mi color favorito es verde", first_prompt)
        self.assertEqual(second_prompt, "¿Y ahora?")

    async def test_calculates_equivalent_api_cost_with_cached_input(self) -> None:
        response = await self.service.ask(123, "Calcula el coste")

        expected = ((8 * 2.00) + (2 * 0.20) + (5 * 12.00)) / 1_000_000
        self.assertAlmostEqual(response.equivalent_api_cost_usd, expected)
        self.assertEqual(response.account_plan, "free")


class ModelCostTests(unittest.TestCase):
    def test_cached_tokens_never_exceed_total_input(self) -> None:
        cost = calculate_api_cost_usd("gpt-5.6-luna", 10, 20, 0)

        self.assertAlmostEqual(cost, (10 * 0.02) / 1_000_000)

    def test_unknown_model_has_no_estimated_cost(self) -> None:
        cost = calculate_api_cost_usd("modelo-desconocido", 10, 0, 5)

        self.assertIsNone(cost)


if __name__ == "__main__":
    unittest.main()
