from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class RegistroAvance:
    componente: str
    objetivo: str
    resultado: str
    archivos: list[str] = field(default_factory=list)
    pruebas: list[str] = field(default_factory=list)
    problemas_pendientes: list[str] = field(default_factory=list)
    proximo_paso: str = ""
    detalles: str = ""


class DocumentationService:
    """Crea documentos Markdown con los avances del Agente IA."""

    def __init__(self, carpeta_avances: Path | str) -> None:
        self.carpeta_avances = Path(carpeta_avances)
        self.carpeta_avances.mkdir(parents=True, exist_ok=True)

    def registrar(self, avance: RegistroAvance) -> Path:
        ahora = datetime.now().astimezone()
        numero = self._siguiente_numero(ahora)
        nombre = self._crear_nombre_archivo(
            fecha=ahora,
            numero=numero,
            componente=avance.componente,
        )

        ruta = self.carpeta_avances / nombre
        contenido = self._crear_markdown(avance, ahora, numero)

        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def _siguiente_numero(self, fecha: datetime) -> int:
        patron = f"{fecha:%Y-%m-%d}_*.md"
        documentos = list(self.carpeta_avances.glob(patron))

        numeros: list[int] = []

        for documento in documentos:
            coincidencia = re.match(
                rf"{fecha:%Y-%m-%d}_(\d{{3}})_",
                documento.name,
            )

            if coincidencia:
                numeros.append(int(coincidencia.group(1)))

        return max(numeros, default=0) + 1

    def _crear_nombre_archivo(
        self,
        fecha: datetime,
        numero: int,
        componente: str,
    ) -> str:
        componente_normalizado = self._normalizar_nombre(componente)

        return (
            f"{fecha:%Y-%m-%d}_"
            f"{numero:03d}_"
            f"{componente_normalizado}.md"
        )

    @staticmethod
    def _normalizar_nombre(texto: str) -> str:
        texto = unicodedata.normalize("NFKD", texto)
        texto = texto.encode("ascii", "ignore").decode("ascii")
        texto = texto.lower().strip()
        texto = re.sub(r"[^a-z0-9]+", "_", texto)
        return texto.strip("_") or "avance"

    def _crear_markdown(
        self,
        avance: RegistroAvance,
        fecha: datetime,
        numero: int,
    ) -> str:
        return f"""# Avance {numero:03d} — {avance.componente}

**Fecha:** {fecha:%d/%m/%Y}
**Hora:** {fecha:%H:%M:%S %Z}
**Componente:** {avance.componente}
**Estado:** {avance.resultado}

## Objetivo

{avance.objetivo}

## Archivos creados o modificados

{self._crear_lista(avance.archivos)}

## Pruebas realizadas

{self._crear_lista(avance.pruebas)}

## Resultado

{avance.resultado}

## Detalles

{avance.detalles or "Sin detalles adicionales."}

## Problemas pendientes

{self._crear_lista(avance.problemas_pendientes)}

## Próximo paso

{avance.proximo_paso or "Pendiente de definir."}
"""

    @staticmethod
    def _crear_lista(elementos: list[str]) -> str:
        if not elementos:
            return "- Ninguno."

        return "\n".join(f"- {elemento}" for elemento in elementos)