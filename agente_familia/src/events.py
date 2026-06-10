import json
import math
from pathlib import Path
from datetime import datetime, timezone

from common.ha_client import HomeAssistantClient
from agente_familia.src.models import HOGARES, SENSORES_ACCESO_CASA
from agente_familia.src.tools import leer_familia
from agente_familia.src.notifications import avisar_jessica

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ESTADO_ANTERIOR_FILE = DATA_DIR / "estado_anterior.json"

VENTANA_PUERTA_MINUTOS = 10


def cargar_estado_anterior() -> dict:
    if not ESTADO_ANTERIOR_FILE.exists():
        return {}

    with open(ESTADO_ANTERIOR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_estado_actual(familia: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    estado = {}

    for persona in familia:
        estado[persona["nombre"]] = {
            "estado": persona["estado"],
            "latitud": persona["latitud"],
            "longitud": persona["longitud"],
            "ultima_actualizacion": persona["ultima_actualizacion"],
        }

    with open(ESTADO_ANTERIOR_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def minutos_desde(fecha_iso: str) -> float | None:
    if not fecha_iso:
        return None

    fecha = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
    ahora = datetime.now(timezone.utc)

    return (ahora - fecha).total_seconds() / 60


def distancia_metros(lat1, lon1, lat2, lon2) -> float | None:
    if None in [lat1, lon1, lat2, lon2]:
        return None

    radio_tierra = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radio_tierra * c


def puerta_abierta_recientemente() -> dict | None:
    ha = HomeAssistantClient()

    for nombre, entity_id in SENSORES_ACCESO_CASA.items():
        datos = ha.get_state(entity_id)

        estado = datos.get("state")
        last_changed = datos.get("last_changed")

        minutos = minutos_desde(last_changed)

        if estado == "on" and minutos is not None and minutos <= VENTANA_PUERTA_MINUTOS:
            return {
                "nombre": nombre,
                "entity_id": entity_id,
                "minutos": minutos,
                "estado": estado,
            }

    return None


def buscar_persona(familia: list[dict], nombre: str) -> dict | None:
    for persona in familia:
        if persona["nombre"].lower() == nombre.lower():
            return persona

    return None


def detectar_llegada_mari_a_casa() -> str:
    familia = leer_familia()
    estado_anterior = cargar_estado_anterior()

    mari = buscar_persona(familia, "Mari")
    casa = HOGARES["Casa"]

    if not mari:
        guardar_estado_actual(familia)
        return "No se encontró información de Mari."

    mari_anterior = estado_anterior.get("Mari", {})
    estado_anterior_mari = mari_anterior.get("estado")

    estaba_fuera = estado_anterior_mari != casa["zona"]

    esta_en_zona = mari["estado"] == casa["zona"]

    distancia = distancia_metros(
        mari["latitud"],
        mari["longitud"],
        casa["latitud"],
        casa["longitud"],
    )

    esta_cerca = (
        distancia is not None
        and distancia <= casa["radio_metros"]
    )

    puerta = puerta_abierta_recientemente()

    guardar_estado_actual(familia)

    if estaba_fuera and puerta and (esta_en_zona or esta_cerca):
        mensaje = (
            "¡Mari ha llegado a Casa!\n"
            f"Estado anterior: {estado_anterior_mari}\n"
            f"Estado actual: {mari['estado']}\n"
            f"Distancia a Casa: {distancia:.0f} metros.\n"
            f"Puerta reciente: sí ({puerta['nombre']}, {puerta['minutos']:.1f} minutos)\n"
        )

        avisar_jessica(mensaje)

        return (
            "Evento detectado: Mari ha llegado a Casa.\n"
            f"{aviso}"
        )






        

    return (
        "No se detecta llegada de Mari a Casa.\n"
        f"Estado anterior: {estado_anterior_mari}\n"
        f"Estado actual: {mari['estado']}\n"
        f"Distancia a Casa: {distancia:.0f} metros.\n"
        f"Puerta reciente: {'sí' if puerta else 'no'}"
    )