from common.ha_client import HomeAssistantClient
from agente_familia.src.models import PERSONAS, HOGARES, GEOCODED_SENSORS
from agente_familia.src.models import HOGARES
from datetime import datetime, timezone


MAX_HORAS_SIN_ACTUALIZAR = 12


def horas_desde(fecha_iso: str) -> float | None:
    if not fecha_iso:
        return None

    fecha = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
    ahora = datetime.now(timezone.utc)

    return (ahora - fecha).total_seconds() / 3600


def detectar_anomalias_familia() -> list[str]:
    familia = leer_familia()
    anomalias = []

    for persona in familia:
        nombre = persona["nombre"]
        estado = persona["estado"]
        tracker = persona["tracker"]
        ultima = persona["ultima_actualizacion"]
        latitud = persona["latitud"]
        longitud = persona["longitud"]
        precision = persona["precision_gps"]
        direccion = persona.get("direccion")

        horas = horas_desde(ultima)

        if not tracker:
            anomalias.append(f"{nombre}: no tiene tracker asociado.")

        if estado in [None, "", "unknown", "unavailable"]:
            anomalias.append(f"{nombre}: estado desconocido.")

        if latitud is None or longitud is None:
            anomalias.append(f"{nombre}: no tiene coordenadas GPS.")

        if not direccion:
            anomalias.append(f"{nombre}: no tiene dirección geográfica disponible.")

        if precision is not None and precision > 200:
            anomalias.append(
                f"{nombre}: precisión GPS baja ({precision} m)."
            )

        if horas is not None and horas > MAX_HORAS_SIN_ACTUALIZAR:
            anomalias.append(
                f"{nombre}: ubicación desactualizada hace {horas:.1f} horas."
            )

    return anomalias


def generar_informe_anomalias() -> str:
    anomalias = detectar_anomalias_familia()

    if not anomalias:
        return "No se han detectado anomalías en las ubicaciones."

    lineas = []
    lineas.append("Anomalías detectadas")
    lineas.append("--------------------")

    for anomalia in anomalias:
        lineas.append(f"- {anomalia}")

    return "\n".join(lineas)
def leer_persona(ha: HomeAssistantClient, nombre: str, entity_id: str) -> dict:
    estado = ha.get_state(entity_id)
    atributos = estado.get("attributes", {})

    direccion = leer_direccion_persona(ha, nombre)

    return {
        "nombre": nombre,
        "entity_id": entity_id,
        "estado": estado.get("state"),
        "direccion": direccion,
        "ultima_actualizacion": estado.get("last_updated"),
        "tracker": atributos.get("source"),
        "latitud": atributos.get("latitude"),
        "longitud": atributos.get("longitude"),
        "precision_gps": atributos.get("gps_accuracy"),
        "nombre_ha": atributos.get("friendly_name"),
    }

def leer_familia() -> list[dict]:
    ha = HomeAssistantClient()

    familia = []

    for nombre, entity_id in PERSONAS.items():
        persona = leer_persona(ha, nombre, entity_id)
        familia.append(persona)

    return familia


def esta_hogar_vacio(nombre_hogar: str) -> dict:
    familia = leer_familia()
    hogar = HOGARES[nombre_hogar]

    zona = hogar["zona"]
    personas_hogar = hogar["personas"]

    presentes = []

    for persona in familia:
        if persona["nombre"] in personas_hogar and persona["estado"] == zona:
            presentes.append(persona["nombre"])

    return {
        "hogar": nombre_hogar,
        "vacio": len(presentes) == 0,
        "presentes": presentes,
    }



def generar_informe_familia() -> str:
    familia = leer_familia()

    lineas = []

    lineas.append("Estado de la familia")
    lineas.append("")

    for persona in familia:
        lineas.append(
            f"{persona['nombre']}: {persona['estado']}"
        )

    lineas.append("")
    lineas.append("Resumen")
    lineas.append("-------")

    for hogar in HOGARES.keys():

        resultado = esta_hogar_vacio(hogar)

        if resultado["vacio"]:
            lineas.append(f"{hogar}: VACÍA")
        else:
            presentes = ", ".join(resultado["presentes"])

            lineas.append(
                f"{hogar}: ocupada ({presentes})"
            )

    return "\n".join(lineas)


def leer_direccion_persona(ha: HomeAssistantClient, nombre: str) -> str | None:
    entity_id = GEOCODED_SENSORS.get(nombre)

    if not entity_id:
        return None

    try:
        datos = ha.get_state(entity_id)

        atributos = datos.get("attributes", {})

        calle = atributos.get("Name")
        ciudad = atributos.get("Locality")
        provincia = atributos.get("Administrative Area")

        partes = []

        if calle:
            partes.append(calle)

        if ciudad:
            partes.append(ciudad)

        if provincia:
            partes.append(provincia)

        if partes:
            return ", ".join(partes)

        return datos.get("state")

    except Exception:
        return None


def generar_informe_localizacion() -> str:
    familia = leer_familia()

    lineas = []

    lineas.append("Localización de personas")
    lineas.append("------------------------")

    for persona in familia:
        nombre = persona["nombre"]
        direccion = persona.get("direccion")
        estado = persona.get("estado")

        if direccion:
            lineas.append(f"{nombre}: {direccion}")
        else:
            lineas.append(f"{nombre}: sin dirección disponible. Estado: {estado}")

    return "\n".join(lineas)

def actualizar_entidad(entity_id: str) -> bool:
    ha = HomeAssistantClient()

    try:
        ha.call_service(
            "homeassistant",
            "update_entity",
            {
                "entity_id": entity_id,
            },
        )
        return True

    except Exception:
        return False
    


def intentar_actualizar_ubicaciones() -> str:
    familia = leer_familia()

    lineas = []
    lineas.append("Actualización de ubicaciones")
    lineas.append("----------------------------")

    for persona in familia:
        nombre = persona["nombre"]
        tracker = persona["tracker"]

        if not tracker:
            lineas.append(f"{nombre}: no tiene tracker asociado.")
            continue

        ok = actualizar_entidad(tracker)

        if ok:
            lineas.append(f"{nombre}: solicitada actualización de {tracker}.")
        else:
            lineas.append(f"{nombre}: no se pudo solicitar actualización de {tracker}.")

    return "\n".join(lineas)