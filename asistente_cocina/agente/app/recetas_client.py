import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("ASISTENTE_COCINA_API")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))

if not API_BASE_URL:
    raise RuntimeError(
        "La variable ASISTENTE_COCINA_API no está definida en el fichero .env"
    )


def _get_json(url: str):
    response = requests.get(url, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def obtener_receta(receta_id: int):
    return _get_json(
        f"{API_BASE_URL}/recetas/{receta_id}"
    )


def obtener_ingredientes(receta_id: int):
    data = _get_json(
        f"{API_BASE_URL}/recetas/{receta_id}/Ingredientes"
    )

    return data.get("content", [])


def obtener_pasos(receta_id: int):
    data = _get_json(
        f"{API_BASE_URL}/recetas/{receta_id}/Pasos"
    )

    return data.get("content", [])