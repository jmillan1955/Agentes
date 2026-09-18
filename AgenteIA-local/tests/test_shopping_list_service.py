from __future__ import annotations

import json
import unittest

import httpx

from agente_ia.shopping_list_service import (
    HomeAssistantShoppingListService,
    ShoppingListServiceError,
    format_shopping_list,
    parse_shopping_list_request,
)


class ShoppingListParserTests(unittest.TestCase):
    def test_queries_both_lists(self) -> None:
        self.assertEqual(parse_shopping_list_request("/lista").list_key, "casa")
        request = parse_shopping_list_request("¿Qué falta comprar en Casa Jessi?")
        self.assertIsNotNone(request)
        self.assertEqual((request.operation, request.list_key), ("list", "casa_jessi"))

    def test_adds_multiple_products(self) -> None:
        request = parse_shopping_list_request(
            "Añade leche, huevos y pan a la lista de Casa"
        )
        self.assertIsNotNone(request)
        self.assertEqual(request.operation, "add")
        self.assertEqual(request.items, ("leche", "huevos", "pan"))

    def test_command_adds_to_jessi(self) -> None:
        request = parse_shopping_list_request("/compra jessi pañales y yogures")
        self.assertIsNotNone(request)
        self.assertEqual(request.list_key, "casa_jessi")
        self.assertEqual(request.items, ("pañales", "yogures"))

    def test_complete_and_remove(self) -> None:
        complete = parse_shopping_list_request("Marca la leche como comprada en Casa")
        remove = parse_shopping_list_request("Borra pañales de Casa Jessi")
        self.assertEqual((complete.operation, complete.items), ("complete", ("leche",)))
        self.assertEqual((remove.operation, remove.list_key), ("remove", "casa_jessi"))
        self.assertTrue(remove.needs_confirmation)

    def test_clear_completed_requires_confirmation(self) -> None:
        request = parse_shopping_list_request("Vacía los productos comprados de Casa")
        self.assertEqual(request.operation, "clear_completed")
        self.assertTrue(request.needs_confirmation)

    def test_does_not_capture_general_question(self) -> None:
        self.assertIsNone(parse_shopping_list_request("¿Cuál es la capital de Portugal?"))
        self.assertIsNone(
            parse_shopping_list_request(
                "¿Qué garantía tiene un coche comprado de segunda mano?"
            )
        )


class ShoppingListServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_items_from_home_assistant_response(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/services/todo/get_items")
            self.assertIn("return_response", str(request.url))
            payload = json.loads(request.content)
            self.assertEqual(payload["entity_id"], "todo.casa")
            return httpx.Response(
                200,
                json={
                    "changed_states": [],
                    "service_response": {
                        "todo.casa": {
                            "items": [
                                {
                                    "summary": "Leche",
                                    "uid": "item-1",
                                    "status": "needs_action",
                                }
                            ]
                        }
                    },
                },
            )

        service = HomeAssistantShoppingListService(
            "http://ha:8123",
            "token",
            {"casa": "todo.casa", "casa_jessi": "todo.casa_jessi"},
            transport=httpx.MockTransport(handler),
        )
        items = await service.items("casa")
        self.assertEqual(format_shopping_list("Casa", items), "Lista de la compra — Casa:\n• Leche")

    async def test_adds_each_product(self) -> None:
        received: list[dict[str, str]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            received.append(json.loads(request.content))
            return httpx.Response(200, json=[])

        service = HomeAssistantShoppingListService(
            "http://ha:8123",
            "token",
            {"casa": "todo.casa"},
            transport=httpx.MockTransport(handler),
        )
        await service.add_items("casa", ("leche", "pan"))
        self.assertEqual([item["item"] for item in received], ["leche", "pan"])

    async def test_reports_missing_item(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"service_response": {"todo.casa": {"items": []}}},
            )

        service = HomeAssistantShoppingListService(
            "http://ha:8123",
            "token",
            {"casa": "todo.casa"},
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(ShoppingListServiceError, "No encuentro"):
            await service.complete_items("casa", ("leche",))


if __name__ == "__main__":
    unittest.main()
