from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace

import aiohttp

from agente_telegram.home_assistant_notification_bridge import (
    EVENT_TYPE,
    MAX_MESSAGE_LENGTH,
    MAX_TITLE_LENGTH,
    HomeAssistantBridgeError,
    HomeAssistantNotificationBridge,
    parse_notification,
    websocket_url,
)
from agente_telegram.telegram_delivery import DeliveryMode


class FakeChannel:
    def __init__(self, *, failures: int = 0) -> None:
        self.calls: list[tuple[str, DeliveryMode]] = []
        self.failures = failures

    async def send(self, text: str, mode: DeliveryMode) -> None:
        self.calls.append((text, mode))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("detalle sensible de Telegram")


class FakeMessage:
    def __init__(self, payload: object) -> None:
        self.type = aiohttp.WSMsgType.TEXT
        self.data = json.dumps(payload)


class FakeWebSocket:
    def __init__(
        self,
        handshake: list[object],
        events: list[FakeMessage] | None = None,
    ) -> None:
        self.handshake = list(handshake)
        self.events = list(events or [])
        self.sent: list[dict[str, object]] = []

    async def receive_json(self) -> object:
        return self.handshake.pop(0)

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    def __aiter__(self) -> FakeWebSocket:
        return self

    async def __anext__(self) -> FakeMessage:
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)


class FakeWebSocketContext:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeSession:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.connect_calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def ws_connect(self, url: str, **kwargs: object) -> FakeWebSocketContext:
        self.connect_calls.append((url, kwargs))
        return FakeWebSocketContext(self.websocket)


def event_payload(data: object) -> dict[str, object]:
    return {
        "type": "event",
        "event": {"event_type": EVENT_TYPE, "data": data},
    }


class PayloadValidationTests(unittest.TestCase):
    def test_websocket_url_preserves_installation_subpath(self) -> None:
        self.assertEqual(
            websocket_url("https://example.test/ha/"),
            "wss://example.test/ha/api/websocket",
        )

    def test_accepts_all_delivery_modes(self) -> None:
        for value, expected in (
            ("text", DeliveryMode.TEXT),
            ("voice", DeliveryMode.VOICE),
            ("both", DeliveryMode.BOTH),
        ):
            with self.subTest(mode=value):
                notification = parse_notification(
                    {"titulo": " Alerta ", "mensaje": " Mensaje ", "modo": value}
                )
                self.assertEqual(notification.mode, expected)
                self.assertEqual(notification.telegram_text, "Alerta\n\nMensaje")

    def test_accepts_missing_title(self) -> None:
        notification = parse_notification({"mensaje": "Mensaje", "modo": "text"})
        self.assertEqual(notification.telegram_text, "Mensaje")

    def test_rejects_invalid_payloads(self) -> None:
        invalid_payloads = (
            None,
            [],
            {},
            {"mensaje": "", "modo": "text"},
            {"mensaje": "Mensaje", "modo": "texto"},
            {"mensaje": 123, "modo": "text"},
            {"titulo": 123, "mensaje": "Mensaje", "modo": "text"},
            {"titulo": "x" * (MAX_TITLE_LENGTH + 1), "mensaje": "m", "modo": "text"},
            {"mensaje": "x" * (MAX_MESSAGE_LENGTH + 1), "modo": "text"},
            {"mensaje": "Mensaje", "modo": "text", "chat_id": -1},
        )
        for payload in invalid_payloads:
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaises(ValueError):
                    parse_notification(payload)


class BridgeProtocolTests(unittest.IsolatedAsyncioTestCase):
    def make_bridge(
        self,
        channel: FakeChannel,
        *,
        session_factory=lambda: None,
        sleep=asyncio.sleep,
    ) -> HomeAssistantNotificationBridge:
        return HomeAssistantNotificationBridge(
            "http://homeassistant.local:8123",
            "secret-token-never-log",
            channel,
            session_factory=session_factory,
            sleep=sleep,
            initial_backoff=1,
            maximum_backoff=4,
        )

    async def test_authenticates_and_subscribes_only_to_dedicated_event(self) -> None:
        websocket = FakeWebSocket(
            [
                {"type": "auth_required"},
                {"type": "auth_ok"},
                {"id": 1, "type": "result", "success": True},
            ]
        )
        session = FakeSession(websocket)
        bridge = self.make_bridge(FakeChannel(), session_factory=lambda: session)

        await bridge._connect_once()

        self.assertEqual(
            websocket.sent,
            [
                {"type": "auth", "access_token": "secret-token-never-log"},
                {"id": 1, "type": "subscribe_events", "event_type": EVENT_TYPE},
            ],
        )
        self.assertEqual(
            session.connect_calls[0][0],
            "ws://homeassistant.local:8123/api/websocket",
        )

    async def test_authentication_failure_does_not_expose_token(self) -> None:
        websocket = FakeWebSocket(
            [{"type": "auth_required"}, {"type": "auth_invalid"}]
        )
        bridge = self.make_bridge(FakeChannel())

        with self.assertRaises(HomeAssistantBridgeError) as caught:
            await bridge._authenticate_and_subscribe(websocket)

        self.assertNotIn("secret-token-never-log", str(caught.exception))

    async def test_delivers_valid_events_in_all_modes(self) -> None:
        channel = FakeChannel()
        websocket = FakeWebSocket(
            [
                {"type": "auth_required"},
                {"type": "auth_ok"},
                {"id": 1, "type": "result", "success": True},
            ],
            [
                FakeMessage(event_payload({"mensaje": "Uno", "modo": "text"})),
                FakeMessage(
                    event_payload(
                        {"titulo": "Aviso", "mensaje": "Dos", "modo": "voice"}
                    )
                ),
                FakeMessage(event_payload({"mensaje": "Tres", "modo": "both"})),
            ],
        )
        bridge = self.make_bridge(
            channel, session_factory=lambda: FakeSession(websocket)
        )

        await bridge._connect_once()

        self.assertEqual(
            channel.calls,
            [
                ("Uno", DeliveryMode.TEXT),
                ("Aviso\n\nDos", DeliveryMode.VOICE),
                ("Tres", DeliveryMode.BOTH),
            ],
        )

    async def test_invalid_events_are_ignored(self) -> None:
        channel = FakeChannel()
        bridge = self.make_bridge(channel)
        invalid_messages = (
            "not json",
            json.dumps({"type": "result"}),
            json.dumps({"type": "event", "event": None}),
            json.dumps(
                {"type": "event", "event": {"event_type": "otro", "data": {}}}
            ),
            json.dumps(event_payload({"mensaje": "", "modo": "text"})),
            json.dumps(
                event_payload(
                    {"mensaje": "No permitido", "modo": "text", "chat_id": -1}
                )
            ),
        )

        for raw_message in invalid_messages:
            await bridge._handle_websocket_text(raw_message)

        self.assertEqual(channel.calls, [])

    async def test_delivery_error_is_isolated_from_next_event(self) -> None:
        channel = FakeChannel(failures=1)
        bridge = self.make_bridge(channel)

        with self.assertLogs(
            "agente_telegram.home_assistant_notification_bridge", level="ERROR"
        ) as captured:
            await bridge._handle_websocket_text(
                json.dumps(event_payload({"mensaje": "Uno", "modo": "text"}))
            )
            await bridge._handle_websocket_text(
                json.dumps(event_payload({"mensaje": "Dos", "modo": "text"}))
            )

        self.assertEqual(len(channel.calls), 2)
        self.assertNotIn("detalle sensible", " ".join(captured.output))
        self.assertNotIn("secret-token-never-log", " ".join(captured.output))

    async def test_reconnects_with_exponential_backoff(self) -> None:
        delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        bridge = self.make_bridge(FakeChannel(), sleep=fake_sleep)
        attempts = 0

        async def connect_once() -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise OSError("HA caído")
            bridge._stop_requested = True

        bridge._connect_once = connect_once  # type: ignore[method-assign]

        await bridge.run_forever()

        self.assertEqual(attempts, 3)
        self.assertEqual(delays, [1, 2])

    async def test_start_and_stop_cancel_background_connection(self) -> None:
        bridge = self.make_bridge(FakeChannel())
        entered = asyncio.Event()
        never_finishes = asyncio.Event()

        async def connect_once() -> None:
            entered.set()
            await never_finishes.wait()

        bridge._connect_once = connect_once  # type: ignore[method-assign]
        bridge.start()
        await asyncio.wait_for(entered.wait(), timeout=1)
        task = bridge._task

        self.assertTrue(bridge.running)
        await bridge.stop()

        self.assertFalse(bridge.running)
        self.assertIsNotNone(task)
        self.assertTrue(task.cancelled())


class AgentBridgeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_starts_and_stops_bridge_cleanly(self) -> None:
        events: list[str] = []

        class FakeStore:
            def initialize(self) -> None:
                events.append("conversation-store-start")

        class FakeWorkflowStore:
            def initialize(self) -> None:
                events.append("workflow-store-start")

        class FakeTelegramChannelLifecycle:
            async def initialize(self) -> None:
                events.append("telegram-start")

            async def shutdown(self) -> None:
                events.append("telegram-stop")

        class FakeBridgeLifecycle:
            def start(self) -> None:
                events.append("bridge-start")

            async def stop(self) -> None:
                events.append("bridge-stop")

        from agente_telegram.bot import TelegramAgent

        agent = object.__new__(TelegramAgent)
        agent.conversation_store = FakeStore()
        agent.task_workflow = SimpleNamespace(store=FakeWorkflowStore())
        agent.notification_channel = FakeTelegramChannelLifecycle()
        agent.home_assistant_notification_bridge = FakeBridgeLifecycle()
        agent.model_services = {}

        await agent.start_service(SimpleNamespace())
        await agent.stop_service(SimpleNamespace())

        self.assertEqual(
            events,
            [
                "conversation-store-start",
                "workflow-store-start",
                "telegram-start",
                "bridge-start",
                "bridge-stop",
                "telegram-stop",
            ],
        )


if __name__ == "__main__":
    unittest.main()
