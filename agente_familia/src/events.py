import json
import math
from pathlib import Path
from datetime import datetime, timezone

from common.ha_client import HomeAssistantClient
from agente_familia.src.models import HOGARES, SENSORES_ACCESO_CASA
from agente_familia.src.tools import leer_familia
from agente_familia.src.notifications import notificar_familia
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ESTADO_ANTERIOR_FILE = DATA_DIR / "estado_anterior.json"

VENTANA_PUERTA_MINUTOS = 10

VENTANA_LLEGADA_MINUTOS = 2

PERSONAS_CASA = {
    "pepe": {
        "nombre": "José",
        "nombre_mensaje": "Pepe",
        "hogar": "Casa",
        "entity_id": "person.jose",
    },
    "mari": {
        "nombre": "Mari",
        "nombre_mensaje": "Mari",
        "hogar": "Casa",
        "entity_id": "person.mari",
    },
}

PERSONAS_CASA_JESSI = {
    "javi": {
        "nombre": "Javi",
        "nombre_mensaje": "Javi",
        "hogar": "Casa Jessi",
        "entity_id": "person.javi",
        "seguimiento": "input_boolean.seguimiento_javi",
    },
    "jessica": {
        "nombre": "Jessica",
        "nombre_mensaje": "Jessica",
        "hogar": "Casa Jessi",
        "entity_id": "person.jessica",
        "seguimiento": "input_boolean.seguimiento_jessica",
    },
}

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


def detectar_llegada_a_casa(persona: str) -> str:

    familia = leer_familia()
    estado_anterior = cargar_estado_anterior()

    alias = persona.lower().strip()

    config_personas = {
        "pepe": {
            "nombre": "José",
            "nombre_mensaje": "Pepe",
            "hogar": "Casa",
            "requiere_puerta": True,
        },
        "jose": {
            "nombre": "José",
            "nombre_mensaje": "Pepe",
            "hogar": "Casa",
            "requiere_puerta": True,
        },
        "josé": {
            "nombre": "José",
            "nombre_mensaje": "Pepe",
            "hogar": "Casa",
            "requiere_puerta": True,
        },
        "mari": {
            "nombre": "Mari",
            "nombre_mensaje": "Mari",
            "hogar": "Casa",
            "requiere_puerta": True,
        },
        "jessica": {
            "nombre": "Jessica",
            "nombre_mensaje": "Jessica",
            "hogar": "Casa Jessi",
            "requiere_puerta": False,
        },
        "javi": {
            "nombre": "Javi",
            "nombre_mensaje": "Javi",
            "hogar": "Casa Jessi",
            "requiere_puerta": False,
        },
    }

    config = config_personas.get(alias)

    if not config:
        guardar_estado_actual(familia)
        return f"Persona no reconocida: {persona}"

    nombre = config["nombre"]
    nombre_mensaje = config["nombre_mensaje"]
    hogar = HOGARES[config["hogar"]]

    datos_persona = buscar_persona(familia, nombre)

    if not datos_persona:
        guardar_estado_actual(familia)
        return f"No se encontró información de {nombre_mensaje}."

    datos_anteriores = estado_anterior.get(nombre, {})
    estado_anterior_persona = datos_anteriores.get("estado")

    estaba_fuera = estado_anterior_persona != hogar["zona"]
    esta_en_zona = datos_persona["estado"] == hogar["zona"]

    distancia = distancia_metros(
        datos_persona["latitud"],
        datos_persona["longitud"],
        hogar["latitud"],
        hogar["longitud"],
    )

    esta_cerca = (
        distancia is not None
        and distancia <= hogar["radio_metros"]
    )

    puerta = None

    if config["requiere_puerta"]:
        puerta = puerta_abierta_recientemente()

    guardar_estado_actual(familia)

    puerta_ok = True

    if config["requiere_puerta"]:
        puerta_ok = puerta is not None

    if estaba_fuera and puerta_ok and (esta_en_zona or esta_cerca):
        nombre_hogar = config["hogar"]

        texto_puerta = ""
        if config["requiere_puerta"]:
            texto_puerta = (
                f"\nPuerta reciente: sí "
                f"({puerta['nombre']}, {puerta['minutos']:.1f} minutos)"
            )

        mensaje = (
            f"{nombre_mensaje} ha vuelto a {nombre_hogar}.\n"
            f"Estado anterior: {estado_anterior_persona}\n"
            f"Estado actual: {datos_persona['estado']}\n"
            f"Distancia a {nombre_hogar}: {distancia:.0f} metros."
            f"{texto_puerta}"
        )

        notificar_familia(
            titulo="Agente Familia",
            mensaje=mensaje,
            personas=[],
        )

        return f"Evento detectado: {nombre_mensaje} ha vuelto a {nombre_hogar}."

    texto_puerta = "no aplica"

    if config["requiere_puerta"]:
        texto_puerta = "sí" if puerta else "no"

    return (

        f"No se detecta llegada de {nombre_mensaje} a {config['hogar']}.\n"
        f"Estado anterior: {estado_anterior_persona}\n"
        f"Estado actual: {datos_persona['estado']}\n"
        f"Distancia a {config['hogar']}: {distancia:.0f} metros.\n"
        f"Puerta reciente: {texto_puerta}"
    )

def minutos_desde_cambio_entidad(entity_id: str) -> float | None:
    ha = HomeAssistantClient()
    datos = ha.get_state(entity_id)

    if not datos:
        return None

    return minutos_desde(datos.get("last_changed"))


def detectar_llegada_por_puerta() -> str:
    familia = leer_familia()
    puerta = puerta_abierta_recientemente()

    if not puerta:
        return "No hay puerta de acceso abierta recientemente."

    eventos = []

    for config in PERSONAS_CASA.values():
        nombre = config["nombre"]
        nombre_mensaje = config["nombre_mensaje"]
        nombre_hogar = config["hogar"]
        hogar = HOGARES[nombre_hogar]

        datos_persona = buscar_persona(familia, nombre)

        if not datos_persona:
            continue

        esta_en_casa = datos_persona["estado"] == hogar["zona"]
        minutos_home = minutos_desde_cambio_entidad(config["entity_id"])

        if (
            esta_en_casa
            and minutos_home is not None
            and minutos_home <= VENTANA_LLEGADA_MINUTOS
        ):
            distancia = distancia_metros(
                datos_persona["latitud"],
                datos_persona["longitud"],
                hogar["latitud"],
                hogar["longitud"],
            )

            mensaje = (
                f"{nombre_mensaje} ha vuelto a {nombre_hogar}.\n"
                f"Estado actual: {datos_persona['estado']}\n"
                f"Tiempo desde llegada a zona: {minutos_home:.1f} minutos.\n"
                f"Distancia a {nombre_hogar}: {distancia:.0f} metros.\n"
                f"Puerta reciente: sí "
                f"({puerta['nombre']}, {puerta['minutos']:.1f} minutos)"
            )

            notificar_familia(
                titulo="Agente Familia",
                mensaje=mensaje,
                personas=[],
            )

            eventos.append(
                f"{nombre_mensaje} ha vuelto a {nombre_hogar}"
            )

    if eventos:
        return "Eventos detectados: " + ", ".join(eventos)

    return (
        "Puerta abierta, pero no se detecta llegada familiar válida. "
        "Nadie de Casa ha cambiado a home en los últimos "
        f"{VENTANA_LLEGADA_MINUTOS} minutos."
    )



def detectar_llegada_por_seguimiento(persona: str) -> str:
    familia = leer_familia()
    alias = persona.lower().strip()

    config = PERSONAS_CASA_JESSI.get(alias)

    if not config:
        return f"Persona no válida para llegada por seguimiento: {persona}"

    ha = HomeAssistantClient()

    seguimiento_activo = ha.get_state(config["seguimiento"]).get("state") == "on"

    if not seguimiento_activo:
        return f"Seguimiento no activo para {config['nombre_mensaje']}."

    nombre = config["nombre"]
    nombre_mensaje = config["nombre_mensaje"]
    nombre_hogar = config["hogar"]
    hogar = HOGARES[nombre_hogar]

    datos_persona = buscar_persona(familia, nombre)

    if not datos_persona:
        return f"No se encontró información de {nombre_mensaje}."

    esta_en_zona = datos_persona["estado"] == hogar["zona"]

    if not esta_en_zona:
        return (
            f"{nombre_mensaje} no está en {nombre_hogar}. "
            f"Estado actual: {datos_persona['estado']}."
        )

    distancia = distancia_metros(
        datos_persona["latitud"],
        datos_persona["longitud"],
        hogar["latitud"],
        hogar["longitud"],
    )

    mensaje = (
        f"{nombre_mensaje} ha llegado a {nombre_hogar}.\n"
        f"Seguimiento activo: sí.\n"
        f"Estado actual: {datos_persona['estado']}.\n"
        f"Distancia a {nombre_hogar}: {distancia:.0f} metros."
    )

    notificar_familia(
        titulo="Agente Familia",
        mensaje=mensaje,
        personas=[alias],
    )

    return f"Evento detectado: {nombre_mensaje} ha llegado a {nombre_hogar}."