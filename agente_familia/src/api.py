import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from agente_familia.src.agent import responder
from agente_familia.src.ai_agent import responder_con_ia
from agente_familia.src.local_ai import responder_local

from agente_familia.src.seguimiento import (
    ejecutar_seguimientos,
    iniciar_seguimiento,
    detener_seguimiento,
    listar_seguimientos,
)

from agente_familia.src.events import (
    detectar_llegada_por_puerta,
    detectar_llegada_por_seguimiento,
)

load_dotenv()

API_KEY = os.getenv("AGENTE_API_KEY")


app = FastAPI(
    title="Agente Familia",
    version="0.4"
)


class PreguntaRequest(BaseModel):
    pregunta: str
class SeguimientoRequest(BaseModel):
    persona: str

def validar_api_key(x_api_key: str | None):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="AGENTE_API_KEY no está configurada"
        )

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="API Key no válida"
        )


@app.get("/health")
def health(x_api_key: str | None = Header(default=None)):
    validar_api_key(x_api_key)

    return {"status": "ok"}


@app.post("/preguntar")
def preguntar(
    datos: PreguntaRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "respuesta": responder(datos.pregunta)
    }

@app.post("/preguntar_ia")
def preguntar_ia(
    datos: PreguntaRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "respuesta": responder_con_ia(datos.pregunta)
    }


@app.post("/preguntar_local")
def preguntar_local(
    datos: PreguntaRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "respuesta": responder_local(datos.pregunta)
    }


@app.get("/seguimiento/listar")
def seguimiento_listar(
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "seguimientos": listar_seguimientos()
    }


@app.post("/seguimiento/iniciar")
def seguimiento_iniciar(
    datos: SeguimientoRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return iniciar_seguimiento(datos.persona)


@app.post("/seguimiento/detener")
def seguimiento_detener(
    datos: SeguimientoRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return detener_seguimiento(datos.persona)


@app.post("/seguimiento/ejecutar")
def seguimiento_ejecutar(
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "resultado": ejecutar_seguimientos()
    }

@app.post("/llegadas/confirmar_por_puerta")
def llegada_confirmar_por_puerta(
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "resultado": detectar_llegada_por_puerta()
    }


@app.post("/llegadas/por_seguimiento")
def llegada_por_seguimiento(
    datos: SeguimientoRequest,
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "resultado": detectar_llegada_por_seguimiento(datos.persona)
    }