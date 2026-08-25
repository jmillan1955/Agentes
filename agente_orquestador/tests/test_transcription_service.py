from pathlib import Path
from types import SimpleNamespace

from app.audio import TranscriptionService


class FakeWhisperModel:
    creations = 0

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
    ) -> None:
        FakeWhisperModel.creations += 1

        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    def transcribe(
        self,
        audio_path: str,
        language: str,
        beam_size: int,
        vad_filter: bool,
        initial_prompt=None,
        hotwords=None,
    ):
        segments = [
            SimpleNamespace(
                text="  Crea el proyecto  "
            ),
            SimpleNamespace(
                text=" puntuacion_padel "
            ),
            SimpleNamespace(
                text="   "
            ),
        ]

        information = {
            "audio_path": audio_path,
            "language": language,
            "beam_size": beam_size,
            "vad_filter": vad_filter,
        }

        return segments, information


def test_transcribes_audio(
    monkeypatch,
) -> None:
    FakeWhisperModel.creations = 0

    monkeypatch.setattr(
        (
            "app.audio.transcription_service"
            ".WhisperModel"
        ),
        FakeWhisperModel,
    )

    service = TranscriptionService(
        model_name="small",
        device="cpu",
        compute_type="int8",
        language="es",
    )

    text = service.transcribe(
        Path("audio.ogg")
    )

    assert (
        text
        == "Crea el proyecto puntuacion_padel"
    )

    assert FakeWhisperModel.creations == 1


def test_loads_model_only_once(
    monkeypatch,
) -> None:
    FakeWhisperModel.creations = 0

    monkeypatch.setattr(
        (
            "app.audio.transcription_service"
            ".WhisperModel"
        ),
        FakeWhisperModel,
    )

    service = TranscriptionService()

    service.transcribe(
        Path("primer_audio.ogg")
    )

    service.transcribe(
        Path("segundo_audio.ogg")
    )

    assert FakeWhisperModel.creations == 1


def test_preserves_configuration(
    monkeypatch,
) -> None:
    FakeWhisperModel.creations = 0

    monkeypatch.setattr(
        (
            "app.audio.transcription_service"
            ".WhisperModel"
        ),
        FakeWhisperModel,
    )

    service = TranscriptionService(
        model_name="medium",
        device="cpu",
        compute_type="int8",
        language="es",
    )

    service.load_model()

    assert service.model_name == "medium"
    assert service.device == "cpu"
    assert service.compute_type == "int8"
    assert service.language == "es"


def test_returns_empty_text_without_segments(
    monkeypatch,
) -> None:
    class EmptyWhisperModel(
        FakeWhisperModel
    ):
        def transcribe(
            self,
            audio_path: str,
            language: str,
            beam_size: int,
            vad_filter: bool,
            initial_prompt=None,
            hotwords=None,
        ):
            return [], {}

    monkeypatch.setattr(
        (
            "app.audio.transcription_service"
            ".WhisperModel"
        ),
        EmptyWhisperModel,
    )

    service = TranscriptionService()

    text = service.transcribe(
        Path("silencio.ogg")
    )

    assert text == ""