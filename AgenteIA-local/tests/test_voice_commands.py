from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from agente_telegram.bot import TelegramAgent
from agente_telegram.voice_commands import ParsedVoiceCommand, parse_voice_command


COMMANDS = (
    "start",
    "mi_id",
    "agenda",
    "evento",
    "aviso_texto",
    "aviso_voz",
    "aviso_ambos",
    "confirmar_audio",
    "corregir_audio",
)


class VoiceCommandParserTests(unittest.TestCase):
    def test_does_not_capture_a_conversational_sentence(self) -> None:
        self.assertIsNone(parse_voice_command("consulta la agenda mañana", COMMANDS))

    def test_accepts_command_without_prefix_when_it_starts_with_command(self) -> None:
        self.assertEqual(
            parse_voice_command(
                "Evento dentista pepe el 20 de octubre a las 12", COMMANDS
            ),
            ParsedVoiceCommand(
                name="evento",
                args=(
                    "dentista",
                    "pepe",
                    "el",
                    "20",
                    "de",
                    "octubre",
                    "a",
                    "las",
                    "12",
                ),
            ),
        )

    def test_matches_longest_registered_name_and_preserves_arguments(self) -> None:
        parsed = parse_voice_command(
            "barra aviso voz mensaje para la familia", COMMANDS
        )

        self.assertEqual(
            parsed,
            ParsedVoiceCommand(
                name="aviso_voz",
                args=("mensaje", "para", "la", "familia"),
            ),
        )

    def test_accepts_start_pronounced_as_estart(self) -> None:
        self.assertEqual(
            parse_voice_command("Barra estart", COMMANDS),
            ParsedVoiceCommand(name="start", args=()),
        )

    def test_accepts_start_pronounced_as_estar(self) -> None:
        self.assertEqual(
            parse_voice_command("Barra estar", COMMANDS),
            ParsedVoiceCommand(name="start", args=()),
        )

    def test_accepts_accents_and_punctuation_before_command(self) -> None:
        self.assertEqual(
            parse_voice_command("¡Barra agenda 14!", COMMANDS),
            ParsedVoiceCommand(name="agenda", args=("14!",)),
        )


class VoiceCommandDispatchTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_contains_all_text_commands(self) -> None:
        agent = object.__new__(TelegramAgent)

        self.assertEqual(
            set(agent.voice_command_handlers()),
            {
                "start",
                "mi_id",
                "debug",
                "nuevo",
                "conversaciones",
                "abrir",
                "historial",
                "ver_plan",
                "responder_tarea",
                "aprobar_tarea",
                "agenda",
                "evento",
                "lista",
                "compra",
                "aviso_texto",
                "aviso_voz",
                "aviso_ambos",
                "modelo",
                "confirmar_audio",
                "corregido",
                "corregir_audio",
                "revisar",
            },
        )

    async def test_dispatch_reuses_handler_and_restores_context_arguments(self) -> None:
        received_args: list[list[str]] = []

        async def handler(update: object, context: object) -> None:
            del update
            received_args.append(list(context.args))

        agent = object.__new__(TelegramAgent)
        agent.voice_command_handlers = lambda: {"aviso_voz": handler}
        context = SimpleNamespace(args=["original"], user_data={}, chat_data={})
        update = SimpleNamespace()

        await agent.dispatch_voice_command(
            update,
            context,
            ParsedVoiceCommand("aviso_voz", ("mensaje", "hablado")),
        )

        self.assertEqual(received_args, [["mensaje", "hablado"]])
        self.assertEqual(context.args, ["original"])
        self.assertNotIn("_voice_command_name", context.__dict__)

    async def test_shopping_command_keeps_slash_when_called_from_voice(self) -> None:
        agent = object.__new__(TelegramAgent)
        agent.settings = SimpleNamespace(allowed_user_ids=(7,))
        agent.procesar_prompt = AsyncMock()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=7),
            message=SimpleNamespace(text=None),
        )
        context = SimpleNamespace(
            args=["casa", "leche"], _voice_command_name="compra"
        )

        await agent.lista_compra_command(update, context)

        self.assertEqual(agent.procesar_prompt.await_args.args[2], "/compra casa leche")


class VoiceMessageFlowTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self, transcription: str) -> TelegramAgent:
        agent = object.__new__(TelegramAgent)
        agent.settings = SimpleNamespace(allowed_user_ids=(7,))
        agent.transcription = SimpleNamespace(
            model_name="test-whisper",
            transcribe=lambda path: transcription,
        )
        agent.responder_debug = AsyncMock()
        agent.responder_telegram = AsyncMock()
        agent.dispatch_voice_command = AsyncMock()
        agent.voice_command_handlers = lambda: {"agenda": object()}
        return agent

    @staticmethod
    def make_update() -> SimpleNamespace:
        return SimpleNamespace(
            effective_user=SimpleNamespace(id=7),
            message=SimpleNamespace(
                voice=SimpleNamespace(file_id="file-id", file_unique_id="voice-test")
            ),
        )

    async def test_recognized_voice_command_skips_review_and_dispatches(self) -> None:
        agent = self.make_agent("barra agenda 14")
        update = self.make_update()

        class FakeBot:
            async def get_file(self, file_id: str) -> object:
                self.file_id = file_id

                class Download:
                    async def download_to_drive(self, custom_path: Path) -> None:
                        custom_path.write_bytes(b"audio")

                return Download()

        context = SimpleNamespace(bot=FakeBot(), user_data={})
        await agent.recibir_voz(update, context)

        parsed = agent.dispatch_voice_command.await_args.args[2]
        self.assertEqual(parsed, ParsedVoiceCommand("agenda", ("14",)))
        self.assertNotIn("pending_audio", context.user_data)
        agent.responder_telegram.assert_not_awaited()

    async def test_non_command_voice_keeps_pending_review_flow(self) -> None:
        agent = self.make_agent("consulta el calendario")
        update = self.make_update()

        class FakeBot:
            async def get_file(self, file_id: str) -> object:
                class Download:
                    async def download_to_drive(self, custom_path: Path) -> None:
                        custom_path.write_bytes(b"audio")

                return Download()

        context = SimpleNamespace(bot=FakeBot(), user_data={})
        await agent.recibir_voz(update, context)

        self.assertEqual(
            context.user_data["pending_audio"], {"text": "consulta el calendario"}
        )
        agent.dispatch_voice_command.assert_not_awaited()
        self.assertIn("consulta el calendario", agent.responder_telegram.await_args.args[1])


if __name__ == "__main__":
    unittest.main()
