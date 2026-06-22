from fastapi import FastAPI

from .models import PrepararRecetaRequest, PrepararRecetaResponse
from .tools import obtener_receta, obtener_ingredientes, obtener_pasos

app = FastAPI(title="Asistente Cocina")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "servicio": "asistente_cocina"
    }


@app.post("/cocina/preparar_receta", response_model=PrepararRecetaResponse)
def preparar_receta(req: PrepararRecetaRequest):
    receta = obtener_receta(req.receta_id)
    ingredientes_respuesta = obtener_ingredientes(req.receta_id)
    pasos_respuesta = obtener_pasos(req.receta_id)

    ingredientes = ingredientes_respuesta.get("content", ingredientes_respuesta)
    pasos = pasos_respuesta.get("content", pasos_respuesta)

    nombre = receta.get("nombre", f"Receta {req.receta_id}")
    peso_racion = float(receta.get("pesoRacion") or receta.get("peso_racion") or 0)

    peso_total_ingredientes = sum(
        float(i.get("cantidad") or 0)
        for i in ingredientes
        if (i.get("unidad") or "g") == "g"
    )

    if req.raciones is not None and req.raciones > 0:
        raciones = req.raciones
    elif peso_racion > 0:
        raciones = round(peso_total_ingredientes / peso_racion, 1)
    else:
        raciones = 0

    resumen = (
        f"Receta preparada: {nombre}. "
        f"Ingredientes: {len(ingredientes)}. "
        f"Pasos: {len(pasos)}. "
        f"Raciones calculadas: {raciones}."
    )

    return PrepararRecetaResponse(
        receta_id=req.receta_id,
        nombre=nombre,
        peso_racion=peso_racion,
        raciones=raciones,
        peso_total_ingredientes=peso_total_ingredientes,
        ingredientes=ingredientes,
        pasos=pasos,
        resumen=resumen,
    )