from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv(
    "ASISTENTE_COCINA_API",
    "https://recetas.jmn55.duckdns.org/api",
).rstrip("/")

API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# Estado global del agente
# ---------------------------------------------------------------------------

estado_lock = threading.RLock()

estado_cocina: dict[str, Any] = {
    "activo": False,
    "receta_id": None,
    "nombre": None,
    "raciones": None,
    "peso_racion": None,
    "ingredientes": [],
    "pasos": [],
    "paso_actual": 0,
    "temporizador_activo": False,
    "temporizador_fin": None,
    "temporizador_duracion_minutos": 0,
    "ultimo_mensaje": "",
}

temporizador_thread: threading.Timer | None = None


# ---------------------------------------------------------------------------
# Funciones auxiliares para consultar la API
# ---------------------------------------------------------------------------

def obtener_json_api(ruta: str) -> Any:
    url = f"{API_BASE_URL}/{ruta.lstrip('/')}"

    respuesta = requests.get(
        url,
        timeout=API_TIMEOUT,
    )

    respuesta.raise_for_status()

    return respuesta.json()


def extraer_content(datos: Any) -> Any:
    """
    La API puede devolver directamente una lista/objeto o envolverla
    dentro de la propiedad 'content'.
    """
    if isinstance(datos, dict) and "content" in datos:
        return datos["content"]

    return datos


def cargar_receta(receta_id: int) -> dict[str, Any]:
    datos = obtener_json_api(f"recetas/{receta_id}")
    receta = extraer_content(datos)

    if not isinstance(receta, dict):
        raise ValueError(
            f"La API no devolvió una receta válida para el ID {receta_id}."
        )

    return receta


def cargar_ingredientes(receta_id: int) -> list[dict[str, Any]]:
    datos = obtener_json_api(
        f"recetas/{receta_id}/Ingredientes"
    )

    ingredientes = extraer_content(datos)

    if ingredientes is None:
        return []

    if not isinstance(ingredientes, list):
        raise ValueError(
            "La API no devolvió una lista válida de ingredientes."
        )

    return ingredientes


def cargar_pasos(receta_id: int) -> list[dict[str, Any]]:
    datos = obtener_json_api(
        f"recetas/{receta_id}/Pasos"
    )

    pasos = extraer_content(datos)

    if pasos is None:
        return []

    if not isinstance(pasos, list):
        raise ValueError(
            "La API no devolvió una lista válida de pasos."
        )

    return sorted(
        pasos,
        key=lambda paso: int(
            paso.get("orden")
            or paso.get("numero")
            or paso.get("id")
            or 0
        ),
    )


# ---------------------------------------------------------------------------
# Funciones auxiliares de estado
# ---------------------------------------------------------------------------

def obtener_nombre_receta(receta: dict[str, Any]) -> str:
    return str(
        receta.get("nombre")
        or receta.get("titulo")
        or receta.get("name")
        or "Receta sin nombre"
    )


def obtener_peso_racion(receta: dict[str, Any]) -> float:
    valor = (
        receta.get("pesoRacion")
        or receta.get("peso_racion")
        or receta.get("pesoPorRacion")
        or 0
    )

    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def obtener_paso_actual() -> dict[str, Any] | None:
    with estado_lock:
        numero_paso = int(estado_cocina["paso_actual"])
        pasos = estado_cocina["pasos"]

        if numero_paso <= 0:
            return None

        if numero_paso > len(pasos):
            return None

        return dict(pasos[numero_paso - 1])


def guardar_ultimo_mensaje(mensaje: str) -> None:
    with estado_lock:
        estado_cocina["ultimo_mensaje"] = mensaje

    print(f"[AGENTE COCINA] {mensaje}", flush=True)


def segundos_restantes_temporizador() -> int:
    with estado_lock:
        if not estado_cocina["temporizador_activo"]:
            return 0

        temporizador_fin = estado_cocina["temporizador_fin"]

    if not temporizador_fin:
        return 0

    try:
        fecha_fin = datetime.fromisoformat(temporizador_fin)
    except (TypeError, ValueError):
        return 0

    diferencia = fecha_fin - datetime.now(timezone.utc)

    return max(0, int(diferencia.total_seconds()))


def construir_respuesta(
    mensaje: str | None = None,
    *,
    ok: bool = True,
    terminado: bool | None = None,
    codigo: str | None = None,
) -> dict[str, Any]:
    with estado_lock:
        activo = bool(estado_cocina["activo"])

        respuesta: dict[str, Any] = {
            "ok": ok,
            "mensaje": (
                mensaje
                if mensaje is not None
                else estado_cocina["ultimo_mensaje"]
            ),
            "activo": activo,
            "receta_id": estado_cocina["receta_id"],
            "receta": estado_cocina["nombre"],
            "raciones": estado_cocina["raciones"],
            "paso_actual": estado_cocina["paso_actual"],
            "paso": obtener_paso_actual(),
            "total_pasos": len(estado_cocina["pasos"]),
            "temporizador_activo": bool(
                estado_cocina["temporizador_activo"]
            ),
            "temporizador_fin": estado_cocina["temporizador_fin"],
            "temporizador_duracion_minutos": estado_cocina[
                "temporizador_duracion_minutos"
            ],
            "temporizador_segundos_restantes":
                segundos_restantes_temporizador(),
            "terminado": (
                not activo
                if terminado is None
                else terminado
            ),
        }

    if codigo:
        respuesta["codigo"] = codigo

    return respuesta


def construir_mensaje_paso(
    paso: dict[str, Any],
    numero_paso: int,
) -> str:
    titulo = str(
        paso.get("nombre")
        or paso.get("titulo")
        or paso.get("descripcion")
        or paso.get("texto")
        or ""
    ).strip()

    descripcion = str(
        paso.get("instrucciones")
        or paso.get("detalle")
        or paso.get("elaboracion")
        or ""
    ).strip()

    duracion = int(paso.get("duracion") or 0)

    partes = [f"Paso {numero_paso}."]

    if titulo:
        partes.append(titulo)

    if descripcion and descripcion != titulo:
        partes.append(descripcion)

    if duracion > 0:
        partes.append(
            f"Este paso tiene un cronómetro de {duracion} minutos. "
            "Pulsa iniciar cronómetro cuando estés preparado."
        )

    return " ".join(partes)


# ---------------------------------------------------------------------------
# Gestión del cronómetro
# ---------------------------------------------------------------------------

def _marcar_temporizador_finalizado() -> None:
    global temporizador_thread

    with estado_lock:
        if not estado_cocina["temporizador_activo"]:
            temporizador_thread = None
            return

        estado_cocina["temporizador_activo"] = False
        estado_cocina["temporizador_fin"] = None
        estado_cocina["temporizador_duracion_minutos"] = 0

        temporizador_thread = None

    mensaje = (
        "El cronómetro ha terminado. "
        "Puedes continuar cuando estés preparado."
    )

    guardar_ultimo_mensaje(mensaje)


def cancelar_temporizador() -> bool:
    global temporizador_thread

    with estado_lock:
        estaba_activo = bool(
            estado_cocina["temporizador_activo"]
        )

        thread = temporizador_thread
        temporizador_thread = None

        estado_cocina["temporizador_activo"] = False
        estado_cocina["temporizador_fin"] = None
        estado_cocina["temporizador_duracion_minutos"] = 0

    if thread is not None:
        thread.cancel()

    return estaba_activo


def iniciar_temporizador(duracion_minutos: int) -> None:
    global temporizador_thread

    if duracion_minutos <= 0:
        raise ValueError(
            "La duración del cronómetro debe ser mayor que cero."
        )

    cancelar_temporizador()

    fecha_fin = (
        datetime.now(timezone.utc)
        + timedelta(minutes=duracion_minutos)
    )

    nuevo_thread = threading.Timer(
        duracion_minutos * 60,
        _marcar_temporizador_finalizado,
    )

    nuevo_thread.daemon = True

    with estado_lock:
        estado_cocina["temporizador_activo"] = True
        estado_cocina["temporizador_fin"] = fecha_fin.isoformat()
        estado_cocina[
            "temporizador_duracion_minutos"
        ] = duracion_minutos

        temporizador_thread = nuevo_thread

    nuevo_thread.start()


def iniciar_cronometro() -> dict[str, Any]:
    with estado_lock:
        if not estado_cocina["activo"]:
            return construir_respuesta(
                "No hay ninguna receta iniciada.",
                ok=False,
                terminado=True,
                codigo="sin_receta",
            )

        if estado_cocina["temporizador_activo"]:
            return construir_respuesta(
                "Ya hay un cronómetro en marcha.",
                ok=False,
                terminado=False,
                codigo="temporizador_activo",
            )

        numero_paso = int(estado_cocina["paso_actual"])
        pasos = estado_cocina["pasos"]

        if numero_paso <= 0 or numero_paso > len(pasos):
            return construir_respuesta(
                "No hay un paso válido seleccionado.",
                ok=False,
                terminado=False,
                codigo="sin_paso",
            )

        paso = dict(pasos[numero_paso - 1])
        duracion = int(paso.get("duracion") or 0)

    if duracion <= 0:
        return construir_respuesta(
            "El paso actual no tiene cronómetro.",
            ok=False,
            terminado=False,
            codigo="sin_duracion",
        )

    iniciar_temporizador(duracion)

    mensaje = (
        f"Cronómetro iniciado para el paso {numero_paso}: "
        f"{duracion} minutos."
    )

    guardar_ultimo_mensaje(mensaje)

    return construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )


def parar_cronometro() -> dict[str, Any]:
    with estado_lock:
        if not estado_cocina["activo"]:
            return construir_respuesta(
                "No hay ninguna receta iniciada.",
                ok=False,
                terminado=True,
                codigo="sin_receta",
            )

        estaba_activo = bool(
            estado_cocina["temporizador_activo"]
        )

    if not estaba_activo:
        return construir_respuesta(
            "No hay ningún cronómetro en marcha.",
            ok=True,
            terminado=False,
        )

    cancelar_temporizador()

    mensaje = "Cronómetro detenido."

    guardar_ultimo_mensaje(mensaje)

    return construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )


# ---------------------------------------------------------------------------
# Estado público del agente
# ---------------------------------------------------------------------------

def obtener_estado() -> dict[str, Any]:
    with estado_lock:
        return {
            "activo": bool(estado_cocina["activo"]),
            "receta_id": estado_cocina["receta_id"],
            "receta": estado_cocina["nombre"],
            "raciones": estado_cocina["raciones"],
            "peso_racion": estado_cocina["peso_racion"],
            "ingredientes": list(
                estado_cocina["ingredientes"]
            ),
            "paso_actual": estado_cocina["paso_actual"],
            "paso": obtener_paso_actual(),
            "total_pasos": len(estado_cocina["pasos"]),
            "temporizador_activo": bool(
                estado_cocina["temporizador_activo"]
            ),
            "temporizador_fin": estado_cocina[
                "temporizador_fin"
            ],
            "temporizador_duracion_minutos": estado_cocina[
                "temporizador_duracion_minutos"
            ],
            "temporizador_segundos_restantes":
                segundos_restantes_temporizador(),
            "ultimo_mensaje": estado_cocina[
                "ultimo_mensaje"
            ],
            "terminado": not bool(
                estado_cocina["activo"]
            ),
        }


# ---------------------------------------------------------------------------
# Inicio y finalización del cocinado
# ---------------------------------------------------------------------------

def limpiar_estado() -> None:
    cancelar_temporizador()

    with estado_lock:
        estado_cocina.update(
            {
                "activo": False,
                "receta_id": None,
                "nombre": None,
                "raciones": None,
                "peso_racion": None,
                "ingredientes": [],
                "pasos": [],
                "paso_actual": 0,
                "temporizador_activo": False,
                "temporizador_fin": None,
                "temporizador_duracion_minutos": 0,
                "ultimo_mensaje": "",
            }
        )


def iniciar_cocinado(
    receta_id: int,
    raciones: float,
) -> dict[str, Any]:
    if receta_id <= 0:
        return {
            "ok": False,
            "mensaje": "El identificador de la receta no es válido.",
            "terminado": True,
            "codigo": "receta_no_valida",
        }

    if raciones <= 0:
        return {
            "ok": False,
            "mensaje": "El número de raciones debe ser mayor que cero.",
            "terminado": True,
            "codigo": "raciones_no_validas",
        }

    try:
        receta = cargar_receta(receta_id)
        ingredientes = cargar_ingredientes(receta_id)
        pasos = cargar_pasos(receta_id)

    except requests.RequestException as error:
        return {
            "ok": False,
            "mensaje": (
                "No se ha podido consultar la API de recetas: "
                f"{error}"
            ),
            "terminado": True,
            "codigo": "error_api",
        }

    except (TypeError, ValueError) as error:
        return {
            "ok": False,
            "mensaje": str(error),
            "terminado": True,
            "codigo": "datos_no_validos",
        }

    if not pasos:
        return {
            "ok": False,
            "mensaje": "La receta no contiene pasos.",
            "terminado": True,
            "codigo": "sin_pasos",
        }

    cancelar_temporizador()

    nombre = obtener_nombre_receta(receta)
    peso_racion = obtener_peso_racion(receta)

    with estado_lock:
        estado_cocina.update(
            {
                "activo": True,
                "receta_id": receta_id,
                "nombre": nombre,
                "raciones": float(raciones),
                "peso_racion": peso_racion,
                "ingredientes": ingredientes,
                "pasos": pasos,
                "paso_actual": 0,
                "temporizador_activo": False,
                "temporizador_fin": None,
                "temporizador_duracion_minutos": 0,
                "ultimo_mensaje": "",
            }
        )

    mensaje = (
        f"Receta {nombre} preparada para "
        f"{raciones:g} raciones. "
        f"Tiene {len(pasos)} pasos."
    )

    guardar_ultimo_mensaje(mensaje)

    respuesta = construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )

    respuesta["ingredientes"] = ingredientes
    respuesta["peso_racion"] = peso_racion

    return respuesta


def finalizar_cocinado() -> dict[str, Any]:
    with estado_lock:
        estaba_activo = bool(estado_cocina["activo"])
        nombre = estado_cocina["nombre"]

    cancelar_temporizador()

    if estaba_activo:
        mensaje = (
            f"La receta {nombre} se ha terminado."
            if nombre
            else "El cocinado se ha terminado."
        )
    else:
        mensaje = "No había ninguna receta activa."

    limpiar_estado()

    return {
        "ok": True,
        "mensaje": mensaje,
        "activo": False,
        "receta_id": None,
        "receta": None,
        "paso_actual": 0,
        "paso": None,
        "total_pasos": 0,
        "temporizador_activo": False,
        "temporizador_fin": None,
        "temporizador_duracion_minutos": 0,
        "temporizador_segundos_restantes": 0,
        "terminado": True,
    }


# ---------------------------------------------------------------------------
# Navegación entre pasos
# ---------------------------------------------------------------------------

def siguiente_paso() -> dict[str, Any]:
    with estado_lock:
        if not estado_cocina["activo"]:
            return construir_respuesta(
                "No hay ninguna receta iniciada.",
                ok=False,
                terminado=True,
                codigo="sin_receta",
            )

        if estado_cocina["temporizador_activo"]:
            return construir_respuesta(
                (
                    "El paso actual tiene un cronómetro activo. "
                    "Detén el cronómetro o espera a que termine."
                ),
                ok=False,
                terminado=False,
                codigo="temporizador_activo",
            )

        indice = int(estado_cocina["paso_actual"])
        pasos = estado_cocina["pasos"]
        nombre = estado_cocina["nombre"]

        if indice >= len(pasos):
            receta_terminada = True
            paso = None
        else:
            receta_terminada = False
            paso = dict(pasos[indice])
            estado_cocina["paso_actual"] = indice + 1

    if receta_terminada:
        mensaje = (
            f"La receta {nombre} ha finalizado. Buen provecho."
        )

        limpiar_estado()

        return {
            "ok": True,
            "mensaje": mensaje,
            "activo": False,
            "receta_id": None,
            "receta": None,
            "paso_actual": 0,
            "paso": None,
            "total_pasos": 0,
            "temporizador_activo": False,
            "temporizador_fin": None,
            "temporizador_duracion_minutos": 0,
            "temporizador_segundos_restantes": 0,
            "terminado": True,
        }

    numero_paso = indice + 1

    mensaje = construir_mensaje_paso(
        paso=paso,
        numero_paso=numero_paso,
    )

    guardar_ultimo_mensaje(mensaje)

    # El cronómetro NO se inicia automáticamente.
    return construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )


def anterior_paso() -> dict[str, Any]:
    with estado_lock:
        if not estado_cocina["activo"]:
            return construir_respuesta(
                "No hay ninguna receta iniciada.",
                ok=False,
                terminado=True,
                codigo="sin_receta",
            )

        if estado_cocina["temporizador_activo"]:
            return construir_respuesta(
                (
                    "El paso actual tiene un cronómetro activo. "
                    "Detén el cronómetro antes de cambiar de paso."
                ),
                ok=False,
                terminado=False,
                codigo="temporizador_activo",
            )

        paso_actual = int(estado_cocina["paso_actual"])
        pasos = estado_cocina["pasos"]

        if paso_actual <= 1:
            estado_cocina["paso_actual"] = 1
            numero_paso = 1
        else:
            numero_paso = paso_actual - 1
            estado_cocina["paso_actual"] = numero_paso

        paso = dict(pasos[numero_paso - 1])

    mensaje = construir_mensaje_paso(
        paso=paso,
        numero_paso=numero_paso,
    )

    guardar_ultimo_mensaje(mensaje)

    return construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )


def repetir_paso() -> dict[str, Any]:
    with estado_lock:
        if not estado_cocina["activo"]:
            return construir_respuesta(
                "No hay ninguna receta iniciada.",
                ok=False,
                terminado=True,
                codigo="sin_receta",
            )

        numero_paso = int(estado_cocina["paso_actual"])
        pasos = estado_cocina["pasos"]

        if numero_paso <= 0 or numero_paso > len(pasos):
            return construir_respuesta(
                "No hay ningún paso para repetir.",
                ok=False,
                terminado=False,
                codigo="sin_paso",
            )

        paso = dict(pasos[numero_paso - 1])

    mensaje = construir_mensaje_paso(
        paso=paso,
        numero_paso=numero_paso,
    )

    guardar_ultimo_mensaje(mensaje)

    return construir_respuesta(
        mensaje,
        ok=True,
        terminado=False,
    )