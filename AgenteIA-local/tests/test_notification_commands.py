from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from agente_telegram.bot import Settings, TelegramAgent
from agente_telegram.telegram_delivery import DeliveryMode


class FakeChannel:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, DeliveryMode]] = []
        self.error = error

    async def send(self, text: str, mode: DeliveryMode) -> None:
        self.calls.append((text, mode))
        if self.error is not None:
            raise self.error


def make_update(user_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(),
    )


def make_agent(channel: FakeChannel | None) -> TelegramAgent:
    agent = object.__new__(TelegramAgent)
    agent.settings = SimpleNamespace(allowed_user_ids=(7,))
    agent.notification_channel = channel
    agent.responder_telegram = AsyncMock()
    return agent


class NotificationCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_conversational_response_uses_common_emitter(self) -> None:
        agent = object.__new__(TelegramAgent)
        agent.telegram_emitter = SimpleNamespace(send_text=AsyncMock())
        bot = object()
        update = SimpleNamespace(
            message=SimpleNamespace(),
            effective_chat=SimpleNamespace(id=55),
            get_bot=Mock(return_value=bot),
        )

        await agent.responder_telegram(update, "Respuesta", provider="interno")

        call = agent.telegram_emitter.send_text.await_args
        self.assertEqual(call.args[:3], (bot, 55, "Respuesta"))
        self.assertIn("Proveedor: interno", call.kwargs["suffix"])

    async def test_authorized_commands_route_all_three_modes(self) -> None:
        channel = FakeChannel()
        agent = make_agent(channel)
        update = make_update()
        context = SimpleNamespace(args=["Mensaje", "de", "prueba"])

        await agent.enviar_aviso_texto(update, context)
        await agent.enviar_aviso_voz(update, context)
        await agent.enviar_aviso_ambos(update, context)

        self.assertEqual(
            channel.calls,
            [
                ("Mensaje de prueba", DeliveryMode.TEXT),
                ("Mensaje de prueba", DeliveryMode.VOICE),
                ("Mensaje de prueba", DeliveryMode.BOTH),
            ],
        )

    async def test_unauthorized_user_cannot_send(self) -> None:
        channel = FakeChannel()
        agent = make_agent(channel)

        await agent.enviar_aviso_texto(
            make_update(user_id=999), SimpleNamespace(args=["No", "enviar"])
        )

        self.assertEqual(channel.calls, [])
        agent.responder_telegram.assert_not_awaited()

    async def test_empty_message_returns_usage_without_sending(self) -> None:
        channel = FakeChannel()
        agent = make_agent(channel)

        await agent.enviar_aviso_voz(make_update(), SimpleNamespace(args=[]))

        self.assertEqual(channel.calls, [])
        self.assertIn(
            "/aviso_voz <mensaje>", agent.responder_telegram.await_args.args[1]
        )

    async def test_missing_channel_is_reported(self) -> None:
        agent = make_agent(None)

        await agent.enviar_aviso_texto(
            make_update(), SimpleNamespace(args=["Mensaje"])
        )

        self.assertIn(
            "no está configurado", agent.responder_telegram.await_args.args[1]
        )

    async def test_delivery_error_is_reported_without_details(self) -> None:
        channel = FakeChannel(RuntimeError("dato sensible"))
        agent = make_agent(channel)

        await agent.enviar_aviso_texto(
            make_update(), SimpleNamespace(args=["Mensaje"])
        )

        response = agent.responder_telegram.await_args.args[1]
        self.assertIn("No se ha podido enviar", response)
        self.assertNotIn("dato sensible", response)


class NotificationSettingsTests(unittest.TestCase):
    def base_environment(self, free: Path, plus: Path) -> dict[str, str]:
        return {
            "HOME": str(free),
            "USERPROFILE": str(free),
            "TELEGRAM_BOT_TOKEN": "conversation-token",
            "TELEGRAM_ALLOWED_USER_IDS": "7,8,7",
            "AGENTEIA_CODEX_HOME_FREE": str(free),
            "AGENTEIA_CODEX_HOME_PLUS": str(plus),
        }

    def read_settings(self, environment: dict[str, str]) -> Settings:
        with patch.dict(os.environ, environment, clear=True), patch(
            "agente_telegram.bot.load_dotenv"
        ):
            return Settings.from_env()

    def test_notification_channel_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            settings = self.read_settings(self.base_environment(path, path))

        self.assertIsNone(settings.notification_telegram_token)
        self.assertIsNone(settings.notification_telegram_chat_id)
        self.assertEqual(settings.allowed_user_ids, (7, 8))
        self.assertFalse(settings.home_assistant_notification_bridge_enabled)

    def test_task_approvers_are_loaded_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment["TELEGRAM_TASK_APPROVER_USER_IDS"] = "8,9,8"
            settings = self.read_settings(environment)

        self.assertEqual(settings.allowed_user_ids, (7, 8))
        self.assertEqual(settings.task_approver_user_ids, (8, 9))

    def test_invalid_task_approver_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment["TELEGRAM_TASK_APPROVER_USER_IDS"] = "usuario"

            with self.assertRaisesRegex(RuntimeError, "TASK_APPROVER"):
                self.read_settings(environment)

    def test_complete_notification_configuration_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment.update(
                {
                    "TELEGRAM_NOTIFICATIONS_BOT_TOKEN": "notification-token",
                    "TELEGRAM_NOTIFICATIONS_CHAT_ID": "-100123456",
                    "TELEGRAM_NOTIFICATIONS_TTS_VOICE": "es-ES-AlvaroNeural",
                }
            )
            settings = self.read_settings(environment)

        self.assertEqual(settings.notification_telegram_token, "notification-token")
        self.assertEqual(settings.notification_telegram_chat_id, -100123456)
        self.assertEqual(settings.notification_tts_voice, "es-ES-AlvaroNeural")

    def test_partial_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment["TELEGRAM_NOTIFICATIONS_BOT_TOKEN"] = "token"

            with self.assertRaisesRegex(RuntimeError, "deben configurarse juntos"):
                self.read_settings(environment)

    def test_non_group_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment.update(
                {
                    "TELEGRAM_NOTIFICATIONS_BOT_TOKEN": "token",
                    "TELEGRAM_NOTIFICATIONS_CHAT_ID": "123",
                }
            )

            with self.assertRaisesRegex(RuntimeError, "valor negativo"):
                self.read_settings(environment)

    def test_invalid_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment.update(
                {
                    "TELEGRAM_NOTIFICATIONS_BOT_TOKEN": "token",
                    "TELEGRAM_NOTIFICATIONS_CHAT_ID": "grupo",
                }
            )

            with self.assertRaisesRegex(RuntimeError, "número entero"):
                self.read_settings(environment)

    def test_bridge_can_be_explicitly_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment["HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED"] = "true"

            settings = self.read_settings(environment)

        self.assertTrue(settings.home_assistant_notification_bridge_enabled)

    def test_invalid_bridge_flag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            environment = self.base_environment(path, path)
            environment["HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED"] = "quizas"

            with self.assertRaisesRegex(RuntimeError, "debe ser true/false"):
                self.read_settings(environment)


if __name__ == "__main__":
    unittest.main()
