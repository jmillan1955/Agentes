from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "es",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: WhisperModel | None = None

    def cargar_modelo(self) -> None:
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

        logger.info("Whisper cargado correctamente")

    def transcribir(self, ruta_audio: Path) -> str:
        self.cargar_modelo()

        if self._model is None:
            raise RuntimeError(
                "El modelo Whisper no está disponible"
            )

        segmentos, _ = self._model.transcribe(
            str(ruta_audio),
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )

        textos = [
            segmento.text.strip()
            for segmento in segmentos
            if segmento.text.strip()
        ]

        return " ".join(textos)