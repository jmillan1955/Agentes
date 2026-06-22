import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_COCINA_URL = os.getenv("API_COCINA_URL", "http://192.168.1.131/api")


def get_json(path: str):
    url = f"{API_COCINA_URL}{path}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def obtener_receta(receta_id: int):
    return get_json(f"/recetas/{receta_id}")


def obtener_ingredientes(receta_id: int):
    return get_json(f"/recetas/{receta_id}/INGREDIENTES")


def obtener_pasos(receta_id: int):
    return get_json(f"/recetas/{receta_id}/pasos")