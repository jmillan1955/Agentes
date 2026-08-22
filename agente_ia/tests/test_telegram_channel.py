from types import SimpleNamespace
import json

from channels.telegram_channel import TelegramChannel


def test_formatea_respuesta_json_para_telegram():
    contenido = json.dumps(
        {
            "respuesta": (
                "Primera línea\nSegunda línea"
            ),
            "tiempo_ejecución_segundos": 6.125,
        },
        ensure_ascii=False,
    )

    resultado = (
        TelegramChannel._formatear_respuesta(
            contenido
        )
    )

    assert "Primera línea\nSegunda línea" in resultado
    assert "\\n" not in resultado
    assert "6.125 segundos" in resultado
    assert "{\"respuesta\"" not in resultado


def test_conserva_respuesta_no_json():
    contenido = "Respuesta normal"

    resultado = (
        TelegramChannel._formatear_respuesta(
            contenido
        )
    )

    assert resultado == contenido

def test_obtiene_voz_desde_caption() -> None:
    canal = TelegramChannel.__new__(
        TelegramChannel
    )
    canal.text_to_speech_service = (
        SimpleNamespace(
            voice="ef_dora"
        )
    )

    voz = canal._obtener_voz_documento(
        "voz = em_alex"
    )

    assert voz == "em_alex"


def test_utiliza_voz_predeterminada_sin_caption() -> None:
    canal = TelegramChannel.__new__(
        TelegramChannel
    )
    canal.text_to_speech_service = (
        SimpleNamespace(
            voice="ef_dora"
        )
    )

    voz = canal._obtener_voz_documento(
        None
    )

    assert voz == "ef_dora"