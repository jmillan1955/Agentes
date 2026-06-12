import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from agente_familia.src.agent import responder
from agente_familia.src.ai_agent import responder_con_ia
from agente_familia.src.local_ai import responder_local
from agente_familia.src.seguimiento import ejecutar_seguimientos

load_dotenv()

API_KEY = os.getenv("AGENTE_API_KEY")


app = FastAPI(
    title="Agente Familia",
    version="0.4"
)


class PreguntaRequest(BaseModel):
    pregunta: str


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

@app.post("/seguimiento/ejecutar")
def ejecutar_seguimiento_manual(
    x_api_key: str | None = Header(default=None)
):
    validar_api_key(x_api_key)

    return {
        "resultado": ejecutar_seguimientos()
    }