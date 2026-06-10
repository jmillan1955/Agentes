from fastapi import FastAPI
from pydantic import BaseModel

from agente_familia.src.agent import responder

app = FastAPI(
    title="Agente Familia",
    version="0.3"
)


class PreguntaRequest(BaseModel):
    pregunta: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/preguntar")
def preguntar(datos: PreguntaRequest):
    return {
        "respuesta": responder(datos.pregunta)
    }