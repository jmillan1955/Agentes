from pydantic import BaseModel
from typing import List


class EvaluarArmadoAusenteRequest(BaseModel):
    origen: str = "home_assistant"
    modo: str = "simulacion"


class SensorEstado(BaseModel):
    entity_id: str
    nombre: str
    estado: str


class EvaluarArmadoAusenteResponse(BaseModel):
    modo: str
    casa_vacia: bool
    pepe: str
    mari: str
    puede_armar: bool
    accion: str
    sensores_abiertos: List[SensorEstado]
    sensores_error: List[SensorEstado]
    resumen: str