from pydantic import BaseModel


class PrepararRecetaRequest(BaseModel):
    receta_id: int
    raciones: float | None = None
    notificar: bool = False


class PrepararRecetaResponse(BaseModel):
    receta_id: int
    nombre: str
    peso_racion: float
    raciones: float
    peso_total_ingredientes: float
    ingredientes: list[dict]
    pasos: list[dict]
    resumen: str