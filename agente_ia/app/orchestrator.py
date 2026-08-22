from __future__ import annotations

from app.models import Peticion, Respuesta
from providers.base import LanguageProvider, ProviderError


class Orchestrator:
    """Coordina el procesamiento de las peticiones."""

    def __init__(
        self,
        language_provider: LanguageProvider | None = None,
    ) -> None:
        self.language_provider = language_provider

    def procesar(self, peticion: Peticion) -> Respuesta:
        contenido = peticion.contenido.strip()

        if not contenido:
            return Respuesta(
                contenido="La petición está vacía.",
                correcto=False,
                peticion_id=peticion.id,
            )

        if contenido.lower() in {
            "ayuda",
            "/ayuda",
            "help",
        }:
            return self._crear_ayuda(peticion)

        if self.language_provider is None:
            return Respuesta(
                contenido=(
                    "He recibido correctamente tu petición:\n\n"
                    f"{contenido}\n\n"
                    "Todavía no tengo conectado el modelo de lenguaje."
                ),
                herramienta="respuesta_provisional",
                peticion_id=peticion.id,
            )

        try:
            contenido_respuesta = (
                self.language_provider.responder(contenido)
            )
        except ProviderError as exc:
            return Respuesta(
                contenido=f"Error del modelo de lenguaje: {exc}",
                correcto=False,
                herramienta="ollama",
                peticion_id=peticion.id,
            )

        return Respuesta(
            contenido=contenido_respuesta,
            correcto=True,
            herramienta="ollama",
            peticion_id=peticion.id,
            metadatos={
                "canal": peticion.canal,
                "tipo_entrada": peticion.tipo.value,
            },
        )

    @staticmethod
    def _crear_ayuda(peticion: Peticion) -> Respuesta:
        return Respuesta(
            contenido=(
                "Capacidades actuales:\n"
                "- Recibir peticiones escritas.\n"
                "- Responder utilizando Qwen mediante Ollama.\n"
                "- Validar peticiones vacías.\n"
                "- Preparar respuestas estructuradas.\n\n"
                "Próximamente:\n"
                "- Registro de herramientas.\n"
                "- Telegram, voz e imágenes."
            ),
            herramienta="ayuda",
            peticion_id=peticion.id,
        )