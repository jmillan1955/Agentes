from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class TextToSpeechError(RuntimeError):
    """Error controlado durante la conversión a voz."""


class TextToSpeechService:
    FRECUENCIA_MUESTREO = 24_000
    VOCES_ESPANOLAS = {
        "ef_dora",
        "em_alex",
        "em_santa",
    }

    def __init__(
        self,
        voice: str = "ef_dora",
        speed: float = 1.0,
        max_characters: int = 20_000,
    ) -> None:
        if voice not in self.VOCES_ESPANOLAS:
            raise ValueError(
                f"Voz Kokoro no válida: {voice}"
            )

        if not 0.5 <= speed <= 2.0:
            raise ValueError(
                "La velocidad debe estar entre 0.5 y 2.0"
            )

        if max_characters <= 0:
            raise ValueError(
                "El límite de caracteres debe ser positivo"
            )

        self.voice = voice
        self.speed = speed
        self.max_characters = max_characters

        self._pipeline: Any | None = None
        self._lock = threading.Lock()

    def generar_mp3(
        self,
        texto: str,
        salida: Path,
    ) -> Path:
        texto = texto.strip()

        if not texto:
            raise TextToSpeechError(
                "El fichero de texto está vacío"
            )

        if len(texto) > self.max_characters:
            raise TextToSpeechError(
                "El texto supera el límite de "
                f"{self.max_characters} caracteres"
            )

        salida = salida.resolve()

        if salida.suffix.lower() != ".mp3":
            raise TextToSpeechError(
                "El fichero de salida debe ser MP3"
            )

        salida.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            with self._lock:
                self._generar_audio(
                    texto=texto,
                    salida=salida,
                )
        except TextToSpeechError:
            raise
        except Exception as error:
            logger.exception(
                "No se pudo generar el audio con Kokoro"
            )
            raise TextToSpeechError(
                "Kokoro no ha podido generar el audio"
            ) from error

        if (
            not salida.is_file()
            or salida.stat().st_size == 0
        ):
            raise TextToSpeechError(
                "Kokoro no ha creado un MP3 válido"
            )

        return salida

    def _obtener_pipeline(self) -> Any:
        if self._pipeline is None:
            logger.info(
                "Cargando Kokoro con idioma español..."
            )

            try:
                from kokoro import KPipeline
            except ImportError as error:
                raise TextToSpeechError(
                    "Kokoro no está instalado"
                ) from error

            self._pipeline = KPipeline(
                lang_code="e"
            )

            logger.info(
                "Kokoro cargado correctamente"
            )

        return self._pipeline

    def _generar_audio(
        self,
        texto: str,
        salida: Path,
    ) -> None:
        try:
            import imageio_ffmpeg
            import numpy as np
            import soundfile as sf
        except ImportError as error:
            raise TextToSpeechError(
                "Faltan dependencias de conversión de audio"
            ) from error

        pipeline = self._obtener_pipeline()
        fragmentos = []

        for _, _, audio in pipeline(
            texto,
            voice=self.voice,
            speed=self.speed,
            split_pattern=r"\n+",
        ):
            fragmentos.append(
                np.asarray(
                    audio,
                    dtype=np.float32,
                )
            )

        if not fragmentos:
            raise TextToSpeechError(
                "Kokoro no ha generado audio"
            )

        audio_completo = np.concatenate(
            fragmentos
        )

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory(
            prefix="agente_ia_kokoro_"
        ) as carpeta:
            wav_temporal = (
                Path(carpeta) / "audio.wav"
            )

            sf.write(
                wav_temporal,
                audio_completo,
                self.FRECUENCIA_MUESTREO,
            )

            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(wav_temporal),
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(salida),
                ],
                check=True,
                capture_output=True,
            )