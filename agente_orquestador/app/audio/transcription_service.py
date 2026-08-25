from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)


DEFAULT_INITIAL_PROMPT = (
    "El usuario habla en español sobre "
    "programación, inteligencia artificial, "
    "bases de datos, aplicaciones y proyectos "
    "de software."
)

DEFAULT_HOTWORDS = (
    "SQLite FastAPI Flask Angular React "
    "JavaScript Python Telegram Whisper Ollama "
    "Kokoro Piper agente_audioText "
    "puntuacion_padel pádel tie-break "
    "punto de oro"
)


class TranscriptionService:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "es",
        initial_prompt: str = DEFAULT_INITIAL_PROMPT,
        hotwords: str = DEFAULT_HOTWORDS,
    ) -> None:
        model_name = model_name.strip()
        device = device.strip()
        compute_type = compute_type.strip()
        language = language.strip()
        initial_prompt = initial_prompt.strip()
        hotwords = hotwords.strip()

        if not model_name:
            raise ValueError(
                "model_name no puede estar vacío"
            )

        if not device:
            raise ValueError(
                "device no puede estar vacío"
            )

        if not compute_type:
            raise ValueError(
                "compute_type no puede estar vacío"
            )

        if not language:
            raise ValueError(
                "language no puede estar vacío"
            )

        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.initial_prompt = (
            initial_prompt or None
        )
        self.hotwords = hotwords or None
        self._model: WhisperModel | None = None

    def load_model(self) -> None:
        if self._model is not None:
            return

        logger.info(
            "Cargando Whisper %s...",
            self.model_name,
        )

        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )

        logger.info(
            "Whisper cargado correctamente"
        )

    def transcribe(
        self,
        audio_path: Path,
    ) -> str:
        self.load_model()

        if self._model is None:
            raise RuntimeError(
                "El modelo Whisper no está disponible"
            )

        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
            initial_prompt=self.initial_prompt,
            hotwords=self.hotwords,
        )

        texts = [
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ]

        transcription = " ".join(texts).strip()

        logger.info(
            "Transcripción terminada: %s caracteres",
            len(transcription),
        )

        return transcription

    def transcribir(
        self,
        ruta_audio: Path,
    ) -> str:
        """
        Mantiene compatibilidad con agente_ia y
        con código que utilice el nombre anterior.
        """
        return self.transcribe(ruta_audio)

    def set_model_for_testing(
        self,
        model: Any,
    ) -> None:
        """
        Permite inyectar un modelo simulado en las
        pruebas sin cargar Whisper realmente.
        """
        self._model = model