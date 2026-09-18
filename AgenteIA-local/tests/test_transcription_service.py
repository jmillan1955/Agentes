from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from agente_telegram.transcription_service import (
    DEFAULT_HOTWORDS,
    TranscriptionService,
)


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def transcribe(self, *args: object, **kwargs: object) -> tuple[list[object], None]:
        self.calls.append((args, kwargs))
        return [SimpleNamespace(text="barra agenda")], None


class TranscriptionServiceTests(unittest.TestCase):
    def test_short_audio_uses_independent_transcription_settings(self) -> None:
        model = FakeWhisperModel()
        service = TranscriptionService()
        service.set_model_for_testing(model)

        self.assertEqual(service.transcribe(Path("nota.ogg")), "barra agenda")

        self.assertEqual(len(model.calls), 1)
        args, kwargs = model.calls[0]
        self.assertEqual(args, ("nota.ogg",))
        self.assertEqual(kwargs["language"], "es")
        self.assertEqual(kwargs["beam_size"], 5)
        self.assertTrue(kwargs["vad_filter"])
        self.assertFalse(kwargs["condition_on_previous_text"])
        self.assertEqual(kwargs["hotwords"], DEFAULT_HOTWORDS)
        self.assertNotIn("initial_prompt", kwargs)

    def test_hotwords_include_spoken_telegram_commands_without_narrative(self) -> None:
        for word in ("barra", "agenda", "evento", "start", "estart", "estar"):
            self.assertIn(word, DEFAULT_HOTWORDS.split())
        self.assertNotIn("El usuario habla", DEFAULT_HOTWORDS)


if __name__ == "__main__":
    unittest.main()
