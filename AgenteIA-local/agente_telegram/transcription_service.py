"""Servicio local de transcripción de notas de voz con Whisper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)

DEFAULT_INITIAL_PROMPT = (
    "El usuario habla en español sobre programación, inteligencia artificial, "
    "bases de datos, aplicaciones y proyectos de software."
)

DEFAULT_HOTWORDS = (
    "SQLite FastAPI Flask Angular React JavaScript Python Telegram Whisper "
    "Codex Luna Terra AgenteIA agente_orquestador agente_telegram"
)


class TranscriptionService:
    """Carga Whisper bajo demanda y devuelve el texto reconocido."""

    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "es",
    ) -> None:
        self.model_name = model_name.strip() or "small"
        self.device = device.strip() or "cpu"
        self.compute_type = compute_type.strip() or "int8"
        self.language = language.strip() or "es"
        self._model: WhisperModel | None = None

    def load_model(self) -> None:
        if self._model is not None:
            return
        logger.info("Cargando Whisper %s...", self.model_name)
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        logger.info("Modelo Whisper cargado correctamente")

    def transcribe(self, audio_path: Path) -> str:
        self.load_model()
        if self._model is None:
            raise RuntimeError("El modelo Whisper no está disponible")

        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
            initial_prompt=DEFAULT_INITIAL_PROMPT,
            hotwords=DEFAULT_HOTWORDS,
        )
        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()
        logger.info("Transcripción terminada: %s caracteres", len(text))
        return text

    def set_model_for_testing(self, model: Any) -> None:
        self._model = model
