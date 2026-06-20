from fastapi import FastAPI
import os
import requests
from dotenv import load_dotenv

from .models import (
    EvaluarArmadoAusenteRequest,
    EvaluarArmadoAusenteResponse,
    SensorEstado,
)

load_dotenv()

HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

app = FastAPI(title="Agente Seguridad")


CONTACTOS_SEGURIDAD = [
    "binary_sensor.ventana_cocina_contact",
    "binary_sensor.ventana_despacho_contact",
    "binary_sensor.ventana_este_salon_bodega_contact",
    "binary_sensor.ventana_grande_salon_contact",
    "binary_sensor.ventana_lateral_salon_contact",

    "binary_sensor.puerta_principal_contact",
    "binary_sensor.puerta_cocina_contact",
    "binary_sensor.puerta_garaje_contact",
    "binary_sensor.puerta_salon_bodega_contact",
]

def leer_estado(entity_id: str):
    url = f"{HA_URL}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def nombre_entidad(datos):
    return datos.get("attributes", {}).get("friendly_name", datos.get("entity_id"))


@app.post(
    "/seguridad/evaluar_armado_ausente",
    response_model=EvaluarArmadoAusenteResponse,
)
def evaluar_armado_ausente(req: EvaluarArmadoAusenteRequest):
    pepe = leer_estado("person.jose")
    mari = leer_estado("person.mari")

    estado_pepe = pepe.get("state")
    estado_mari = mari.get("state")

    casa_vacia = estado_pepe != "home" and estado_mari != "home"

    sensores_abiertos = []
    sensores_error = []

    for entidad in CONTACTOS_SEGURIDAD:
        try:
            datos = leer_estado(entidad)
            estado = datos.get("state")
            nombre = nombre_entidad(datos)

            sensor = SensorEstado(
                entity_id=entidad,
                nombre=nombre,
                estado=estado,
            )

            if estado == "on":
                sensores_abiertos.append(sensor)

            elif estado in ["unknown", "unavailable"]:
                sensores_error.append(sensor)

        except Exception as e:
            sensores_error.append(
                SensorEstado(
                    entity_id=entidad,
                    nombre=entidad,
                    estado=f"error: {e}",
                )
            )

    puede_armar = (
        casa_vacia
        and len(sensores_abiertos) == 0
        and len(sensores_error) == 0
    )

    if not casa_vacia:
        resumen = (
            "SIMULACIÓN: No se recomienda armar Alarmo Ausente porque "
            f"la casa no parece vacía. Pepe={estado_pepe}, Mari={estado_mari}."
        )
        accion = "no_armar"

    elif sensores_error:
        nombres = ", ".join([s.nombre for s in sensores_error])
        resumen = (
            "SIMULACIÓN: La casa parece vacía, pero no se recomienda armar "
            f"porque hay sensores con error o sin datos: {nombres}."
        )
        accion = "no_armar"

    elif sensores_abiertos:
        nombres = ", ".join([s.nombre for s in sensores_abiertos])
        resumen = (
            "SIMULACIÓN: La casa parece vacía, pero no se recomienda armar "
            f"porque hay sensores abiertos: {nombres}."
        )
        accion = "no_armar"

    else:
        resumen = (
            "SIMULACIÓN: La casa parece vacía y todos los sensores de contacto "
            "están cerrados. Se podría armar Alarmo Ausente."
        )
        accion = "simular_armar_ausente"




    print("========== EVALUACIÓN SEGURIDAD ==========")
    print(f"Pepe: {estado_pepe}")
    print(f"Mari: {estado_mari}")
    print(f"Casa vacía: {casa_vacia}")
    print(f"Sensores abiertos: {len(sensores_abiertos)}")
    print(f"Sensores error: {len(sensores_error)}")
    print(f"Acción: {accion}")
    print("==========================================")




    return EvaluarArmadoAusenteResponse(
        modo=req.modo,
        casa_vacia=casa_vacia,
        pepe=estado_pepe,
        mari=estado_mari,
        puede_armar=puede_armar,
        accion=accion,
        sensores_abiertos=sensores_abiertos,
        sensores_error=sensores_error,
        resumen=resumen,
    )