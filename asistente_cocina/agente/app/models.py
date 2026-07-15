from pydantic import BaseModel


class IniciarCocinadoRequest(BaseModel):
    receta_id: int
    raciones: float


class RespuestaAgente(BaseModel):
    ok: bool
    mensaje: str
    paso_actual: int | None = None
    terminado: bool = False