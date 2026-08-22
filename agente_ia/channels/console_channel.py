from __future__ import annotations

from app.models import Peticion
from app.orchestrator import Orchestrator
from config import Settings


class ConsoleChannel:
    def __init__(
        self,
        settings: Settings,
        orchestrator: Orchestrator,
    ) -> None:
        self.settings = settings
        self.orchestrator = orchestrator

    def ejecutar(self) -> None:
        self._mostrar_cabecera()

        while True:
            try:
                texto = input("Tú: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAgente IA finalizado.")
                break

            if texto.lower() in {
                "/salir",
                "salir",
                "exit",
            }:
                print("Agente IA finalizado.")
                break

            peticion = Peticion(
                contenido=texto,
                canal="consola",
            )

            respuesta = self.orchestrator.procesar(
                peticion
            )

            print()
            print(f"Agente IA: {respuesta.contenido}")
            print()

    def _mostrar_cabecera(self) -> None:
        print("=" * 60)
        print(
            f"{self.settings.nombre} "
            f"{self.settings.version}"
        )
        print(f"Entorno: {self.settings.entorno}")
        print(f"Modelo: {self.settings.ollama_model}")
        print(f"Ollama: {self.settings.ollama_url}")
        print("=" * 60)
        print("Escribe una petición.")
        print("Comandos: /ayuda y /salir")
        print()