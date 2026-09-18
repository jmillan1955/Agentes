from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agente_telegram.telegram_delivery import (
    DeliveryMode,
    FixedTelegramChannel,
    TelegramEmitter,
    split_telegram_text,
)


class FakeBot:
    def __init__(self, *, voice_error: Exception | None = None) -> None:
        self.messages: list[dict[str, object]] = []
        self.voices: list[dict[str, object]] = []
        self.voice_error = voice_error
        self.initialized = False
        self.stopped = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.stopped = True

    async def send_message(self, **kwargs: object) -> None:
        self.messages.append(kwargs)

    async def send_voice(self, **kwargs: object) -> None:
        voice = kwargs["voice"]
        self.assert_open(voice)
        self.voices.append(
            {**kwargs, "voice": voice.read(), "source_name": voice.name}
        )
        if self.voice_error is not None:
            raise self.voice_error

    @staticmethod
    def assert_open(stream: object) -> None:
        if getattr(stream, "closed", True):
            raise AssertionError("El audio se cerró antes de enviarlo")


class FakeSynthesizer:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.paths: list[Path] = []

    async def synthesize(self, text: str, output_path: Path) -> None:
        self.paths.append(output_path)
        if self.error is not None:
            raise self.error
        output_path.write_bytes(f"audio:{text}".encode())


class TelegramTextTests(unittest.IsolatedAsyncioTestCase):
    def test_split_preserves_all_content_and_limit(self) -> None:
        text = "palabra " * 1300
        suffix = "pie informativo"
        parts = split_telegram_text(text, suffix=suffix, limit=200)

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 200 for part in parts))
        self.assertTrue(all(part.endswith(suffix) for part in parts))
        recovered = " ".join(part.removesuffix("\n\n" + suffix) for part in parts)
        self.assertEqual(recovered.split(), text.split())

    async def test_send_text_places_keyboard_only_on_last_fragment(self) -> None:
        bot = FakeBot()
        emitter = TelegramEmitter()
        keyboard = object()

        await emitter.send_text(
            bot,
            -123,
            "x" * 5000,
            suffix="pie",
            reply_markup=keyboard,
        )

        self.assertEqual(len(bot.messages), 2)
        self.assertIsNone(bot.messages[0]["reply_markup"])
        self.assertIs(bot.messages[1]["reply_markup"], keyboard)
        self.assertTrue(all(item["chat_id"] == -123 for item in bot.messages))


class TelegramVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_uses_fixed_destination_and_cleans_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bot = FakeBot()
            synth = FakeSynthesizer()
            channel = FixedTelegramChannel(
                bot,
                -987654,
                TelegramEmitter(synthesizer=synth, temp_root=root),
            )

            await channel.send("Puerta abierta", DeliveryMode.VOICE)

            self.assertEqual(bot.voices[0]["chat_id"], -987654)
            self.assertEqual(bot.voices[0]["voice"], b"audio:Puerta abierta")
            self.assertFalse(synth.paths[0].exists())
            self.assertEqual(list(root.iterdir()), [])

    async def test_both_sends_text_then_voice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bot = FakeBot()
            channel = FixedTelegramChannel(
                bot,
                -44,
                TelegramEmitter(
                    synthesizer=FakeSynthesizer(),
                    temp_root=Path(temporary),
                ),
            )

            await channel.send("Aviso doble", DeliveryMode.BOTH)

            self.assertEqual([item["text"] for item in bot.messages], ["Aviso doble"])
            self.assertEqual(len(bot.voices), 1)

    async def test_text_mode_does_not_require_synthesizer(self) -> None:
        bot = FakeBot()
        channel = FixedTelegramChannel(bot, -2, TelegramEmitter())

        await channel.send("Solo texto", DeliveryMode.TEXT)

        self.assertEqual(len(bot.messages), 1)
        self.assertEqual(bot.voices, [])

    async def test_synthesis_error_still_cleans_temporary_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            synth = FakeSynthesizer(error=RuntimeError("fallo TTS"))
            channel = FixedTelegramChannel(
                FakeBot(),
                -2,
                TelegramEmitter(synthesizer=synth, temp_root=root),
            )

            with self.assertRaisesRegex(RuntimeError, "fallo TTS"):
                await channel.send("Falla", DeliveryMode.VOICE)

            self.assertFalse(synth.paths[0].exists())
            self.assertEqual(list(root.iterdir()), [])

    async def test_send_error_still_cleans_temporary_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            synth = FakeSynthesizer()
            channel = FixedTelegramChannel(
                FakeBot(voice_error=RuntimeError("fallo Telegram")),
                -2,
                TelegramEmitter(synthesizer=synth, temp_root=root),
            )

            with self.assertRaisesRegex(RuntimeError, "fallo Telegram"):
                await channel.send("Falla", DeliveryMode.VOICE)

            self.assertFalse(synth.paths[0].exists())
            self.assertEqual(list(root.iterdir()), [])

    async def test_channel_lifecycle_is_forwarded_to_bot(self) -> None:
        bot = FakeBot()
        channel = FixedTelegramChannel(bot, -2, TelegramEmitter())

        await channel.initialize()
        await channel.shutdown()

        self.assertTrue(bot.initialized)
        self.assertTrue(bot.stopped)


if __name__ == "__main__":
    unittest.main()
