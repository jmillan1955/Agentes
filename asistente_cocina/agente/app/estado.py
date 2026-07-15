from threading import Lock
from typing import Any


estado_lock = Lock()

estado_cocina: dict[str, Any] = {
    "activo": False,
    "receta_id": None,
    "nombre": None,
    "raciones": None,
    "ingredientes": [],
    "pasos": [],
    "paso_actual": 0,
    "temporizador_activo": False,
    "temporizador_fin": None,
    "ultimo_mensaje": None,
}


def limpiar_estado() -> None:
    with estado_lock:
        estado_cocina.update({
            "activo": False,
            "receta_id": None,
            "nombre": None,
            "raciones": None,
            "ingredientes": [],
            "pasos": [],
            "paso_actual": 0,
            "temporizador_activo": False,
            "temporizador_fin": None,
            "ultimo_mensaje": None,
        })