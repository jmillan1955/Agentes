from pathlib import Path

import pytest

from app.text_to_speech_service import (
    TextToSpeechError,
    TextToSpeechService,
)


def test_genera_fichero_mp3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    servicio = TextToSpeechService(
        voice="ef_dora",
        speed=1.0,
        max_characters=100,
    )

    salida = tmp_path / "resultado.mp3"

    def generar_simulado(
        texto: str,
        salida: Path,
    ) -> None:
        assert texto == "Texto de prueba"
        salida.write_bytes(b"mp3-simulado")

    monkeypatch.setattr(
        servicio,
        "_generar_audio",
        generar_simulado,
    )

    resultado = servicio.generar_mp3(
        "Texto de prueba",
        salida,
    )

    assert resultado == salida.resolve()
    assert resultado.is_file()
    assert resultado.read_bytes() == b"mp3-simulado"


def test_rechaza_texto_vacio(
    tmp_path: Path,
) -> None:
    servicio = TextToSpeechService()
    salida = tmp_path / "resultado.mp3"

    with pytest.raises(
        TextToSpeechError,
        match="vacío",
    ):
        servicio.generar_mp3(
            "   ",
            salida,
        )


def test_rechaza_texto_demasiado_largo(
    tmp_path: Path,
) -> None:
    servicio = TextToSpeechService(
        max_characters=10
    )
    salida = tmp_path / "resultado.mp3"

    with pytest.raises(
        TextToSpeechError,
        match="supera el límite",
    ):
        servicio.generar_mp3(
            "Este texto tiene más de diez caracteres",
            salida,
        )


def test_rechaza_extension_distinta_de_mp3(
    tmp_path: Path,
) -> None:
    servicio = TextToSpeechService()
    salida = tmp_path / "resultado.wav"

    with pytest.raises(
        TextToSpeechError,
        match="debe ser MP3",
    ):
        servicio.generar_mp3(
            "Texto de prueba",
            salida,
        )


def test_rechaza_voz_desconocida() -> None:
    with pytest.raises(
        ValueError,
        match="Voz Kokoro no válida",
    ):
        TextToSpeechService(
            voice="voz_inexistente"
        )


@pytest.mark.parametrize(
    "velocidad",
    [0.49, 2.01],
)
def test_rechaza_velocidad_fuera_de_rango(
    velocidad: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="velocidad debe estar",
    ):
        TextToSpeechService(
            speed=velocidad
        )