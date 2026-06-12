import json
import math
from pathlib import Path
from datetime import datetime

from common.ha_client import HomeAssistantClient
from agente_familia.src.models import GEOCODED_SENSORS, SEGUIMIENTO_PERSONAS, PERSON_ENTITY_IDS
from agente_familia.src.notifications import notificar_familia


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "seguimientos.json"


def cargar_seguimientos() -> dict:
    if not DATA_FILE.exists():
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)



def guardar_seguimientos(seguimientos: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(seguimientos, f, ensure_ascii=False, indent=2)


def listar_seguimientos() -> dict:
    return cargar_seguimientos()


def iniciar_seguimiento(persona: str) -> dict:
    alias = persona.lower().strip()

    if alias not in SEGUIMIENTO_PERSONAS:
        return {
            "ok": False,
            "mensaje": f"Persona no reconocida: {persona}",
            "seguimientos": cargar_seguimientos(),
        }

    seguimientos = cargar_seguimientos()

    seguimientos[alias] = {
        "activo": True
    }

    guardar_seguimientos(seguimientos)

    return {
        "ok": True,
        "mensaje": f"Seguimiento iniciado para {alias}",
        "seguimientos": seguimientos,
    }


def detener_seguimiento(persona: str) -> dict:
    alias = persona.lower().strip()

    if alias not in SEGUIMIENTO_PERSONAS:
        return {
            "ok": False,
            "mensaje": f"Persona no reconocida: {persona}",
            "seguimientos": cargar_seguimientos(),
        }

    seguimientos = cargar_seguimientos()

    if alias not in seguimientos:
        seguimientos[alias] = {
            "activo": False
        }
    else:
        seguimientos[alias]["activo"] = False

    guardar_seguimientos(seguimientos)

    return {
        "ok": True,
        "mensaje": f"Seguimiento detenido para {alias}",
        "seguimientos": seguimientos,
    }


def extraer_location(atributos: dict) -> list[float] | None:
    location = atributos.get("Location") or atributos.get("location")

    if not location:
        return None

    if isinstance(location, list) and len(location) >= 2:
        return [float(location[0]), float(location[1])]

    if isinstance(location, str):
        partes = [p.strip() for p in location.split(",")]

        if len(partes) >= 2:
            return [float(partes[0]), float(partes[1])]

    return None


def construir_direccion(atributos: dict, estado: str | None = None) -> str:
    name = atributos.get("Name") or atributos.get("name")
    thoroughfare = atributos.get("Thoroughfare") or atributos.get("thoroughfare")
    numero = atributos.get("Sub Thoroughfare") or atributos.get("sub_thoroughfare")
    locality = atributos.get("Locality") or atributos.get("locality")
    postal_code = atributos.get("Postal Code") or atributos.get("postal_code")

    
    if thoroughfare and numero:
        calle = f"{thoroughfare}, {numero}"
    elif thoroughfare:
        calle = str(thoroughfare)
    elif name:
        calle = str(name)
    else:
        calle = estado or "Dirección no disponible"

    lineas = [calle]

    segunda_linea = []

    if postal_code:
        segunda_linea.append(str(postal_code))

    if locality:
        segunda_linea.append(str(locality))

    if segunda_linea:
        lineas.append(" ".join(segunda_linea))

    return "\n".join(lineas)


def obtener_posicion(nombre: str) -> dict | None:
    ha = HomeAssistantClient()
    entity_id = GEOCODED_SENSORS.get(nombre)

    if not entity_id:
        return None

    datos_geo = ha.get_state(entity_id)
    atributos = datos_geo.get("attributes", {})
    location = extraer_location(atributos)

    person_entity = PERSON_ENTITY_IDS.get(nombre)
    datos_persona = ha.get_state(person_entity) if person_entity else {}

    return {
        "entity_id": entity_id,
        "estado": datos_persona.get("state") or datos_geo.get("state"),
        "latitud": location[0],
        "longitud": location[1],
        "direccion": construir_direccion(atributos, datos_geo.get("state")),
        "last_changed": datos_persona.get("last_changed"),
        "last_updated": datos_persona.get("last_updated"),
    }


def leer_zonas() -> list[dict]:
    ha = HomeAssistantClient()
    estados = ha.get_states()

    zonas = []

    for entidad in estados:
        entity_id = entidad.get("entity_id", "")

        if not entity_id.startswith("zone."):
            continue

        atributos = entidad.get("attributes", {})

        latitud = atributos.get("latitude")
        longitud = atributos.get("longitude")

        if latitud is None or longitud is None:
            continue

        zonas.append(
            {
                "entity_id": entity_id,
                "nombre": atributos.get("friendly_name", entity_id),
                "latitud": float(latitud),
                "longitud": float(longitud),
                "radio": float(atributos.get("radius", 0)),
            }
        )

    return zonas


def distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def zona_mas_cercana(latitud: float, longitud: float) -> dict | None:
    zonas = leer_zonas()

    mejor = None

    for zona in zonas:
        distancia = distancia_metros(
            latitud,
            longitud,
            zona["latitud"],
            zona["longitud"],
        )

        dentro = distancia <= zona["radio"]

        if mejor is None or distancia < mejor["distancia_m"]:
            mejor = {
                "zona": zona["nombre"],
                "entity_id": zona["entity_id"],
                "distancia_m": distancia,
                "radio_m": zona["radio"],
                "dentro": dentro,
            }

    return mejor


def formatear_distancia(metros: float) -> str:
    if metros < 1000:
        return f"{metros:.0f} m"

    return f"{metros / 1000:.1f} km"


def formatear_fecha(fecha_iso: str | None) -> str:
    if not fecha_iso:
        return "No disponible"

    try:
        fecha = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
        return fecha.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return fecha_iso


def crear_mensaje_seguimiento(nombre: str, posicion: dict) -> str:
    zona = zona_mas_cercana(posicion["latitud"], posicion["longitud"])

    if zona:
        texto_zona = (
            f"Zona más cercana:\n"
            f"{zona['zona']}\n\n"
            f"Distancia:\n"
            f"{formatear_distancia(zona['distancia_m'])}\n\n"
            f"Dentro de zona:\n"
            f"{'Sí' if zona['dentro'] else 'No'}"
        )
    else:
        texto_zona = (
            "Zona más cercana:\n"
            "No disponible"
        )

    return (
        f"Seguimiento de {nombre}\n\n"
        f"Dirección:\n"
        f"{posicion['direccion']}\n\n"
        f"{texto_zona}\n\n"
        f"Last updated:\n"
        f"{formatear_fecha(posicion['last_updated'])}\n\n"
        f"Last changed:\n"
        f"{formatear_fecha(posicion['last_changed'])}"
)


def ejecutar_seguimientos() -> str:
    seguimientos = cargar_seguimientos()
    avisos = []

    for alias, config in seguimientos.items():
        if not config.get("activo"):
            continue

        nombre = SEGUIMIENTO_PERSONAS.get(alias)

        if not nombre:
            avisos.append(f"{alias}: persona no reconocida")
            continue

        actualizar_entidades_persona(nombre)
        posicion = obtener_posicion(nombre)

        if not posicion:
            avisos.append(f"{nombre}: sin posición disponible")
            continue

        mensaje = crear_mensaje_seguimiento(nombre, posicion)

        notificar_familia(
            titulo="Agente Familia - Seguimiento",
            mensaje=mensaje,
            personas=[alias],
        )

        avisos.append(f"Enviado seguimiento de {nombre}")

    return "\n".join(avisos) if avisos else "No hay seguimientos activos."


def actualizar_entidades_persona(nombre: str) -> list[str]:
    ha = HomeAssistantClient()
    entidades = []

    persona_entity = None

    for alias, persona_nombre in SEGUIMIENTO_PERSONAS.items():
        if persona_nombre == nombre:
            break

    # Mapeo directo recomendado
    entidades_por_persona = {
        "José": [
            "person.jose",
            "device_tracker.movil_pepe",
            "sensor.movil_pepe_geocoded_location",
        ],
        "Mari": [
            "person.mari",
            "device_tracker.mari_carmen",
            "sensor.mari_carmen_geocoded_location",
        ],
        "Jessica": [
            "person.jessica",
            "device_tracker.iphone_de_jess",
            "sensor.iphone_de_jess_geocoded_location",
        ],
        "Javi": [
            "person.javi",
            "device_tracker.javi_movil",
            "sensor.javi_movil_geocoded_location",
        ],
    }

    entidades = entidades_por_persona.get(nombre, [])

    actualizadas = []

    for entity_id in entidades:
        try:
            ha.call_service(
                "homeassistant",
                "update_entity",
                {
                    "entity_id": entity_id
                },
            )
            actualizadas.append(entity_id)
        except Exception as e:
            actualizadas.append(f"{entity_id} ERROR {e}")

    return actualizadas


if __name__ == "__main__":
    print(ejecutar_seguimientos())