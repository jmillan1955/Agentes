from fastapi import FastAPI

from app import cocina_service
from app.models import IniciarCocinadoRequest

app = FastAPI(title="Agente Cocina")


@app.get("/salud")
def salud():
    return {
        "estado": "ok",
        "agente": "cocina",
    }


@app.get("/cocina/estado")
def estado():
    return cocina_service.obtener_estado()


@app.post("/cocina/iniciar")
def iniciar(request: IniciarCocinadoRequest):
    return cocina_service.iniciar_cocinado(
        receta_id=request.receta_id,
        raciones=request.raciones,
    )


@app.post("/cocina/siguiente")
def siguiente():
    return cocina_service.siguiente_paso()


@app.post("/cocina/anterior")
def anterior():
    return cocina_service.anterior_paso()


@app.post("/cocina/repetir")
def repetir():
    return cocina_service.repetir_paso()


@app.post("/cocina/finalizar")
def finalizar():
    return cocina_service.finalizar_cocinado()

@app.post("/cocina/cronometro/iniciar")
def iniciar_cronometro():
    return cocina_service.iniciar_cronometro()


@app.post("/cocina/cronometro/parar")
def parar_cronometro():
    return cocina_service.parar_cronometro()