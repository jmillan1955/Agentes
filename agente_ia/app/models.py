from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class TipoEntrada(str, Enum):
    TEXTO = "texto"
    AUDIO = "audio"
    IMAGEN = "imagen"
    DOCUMENTO = "documento"


class TipoSalida(str, Enum):
    TEXTO = "texto"
    AUDIO = "audio"
    IMAGEN = "imagen"
    DOCUMENTO = "documento"
    JSON = "json"


@dataclass
class Peticion:
    contenido: str
    canal: str = "consola"
    tipo: TipoEntrada = TipoEntrada.TEXTO
    archivos: list[str] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)
    id: str = field(
        default_factory=lambda: str(uuid4())
    )


@dataclass
class Respuesta:
    contenido: str
    tipo: TipoSalida = TipoSalida.TEXTO
    correcto: bool = True
    herramienta: str | None = None
    archivos: list[str] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)
    peticion_id: str | None = None