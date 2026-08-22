from __future__ import annotations

import httpx
import json
import time
from providers.base import ProviderError


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def responder(self, texto: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres el Agente IA de José. "
                        "Responde siempre en español, de forma clara, "
                        "práctica y directa. Devuelve exclusivamente "
                        "la respuesta final solicitada."
                    ),
                },
                {
                    "role": "user",
                    "content": f"/no_think\n{texto}",
                },
            ],
            "stream": False,
            "think": False,
            "format": {
                "type": "object",
                "properties": {
                    "respuesta": {
                        "type": "string"
                    }
                },
                "required": ["respuesta"],
            },
            "options": {
                "num_predict": 1200,
                "temperature": 0.2,
            },
        }
        try:
            timeout = httpx.Timeout(
                connect=10.0,
                read=300.0,
                write=30.0,
                pool=10.0,
            )
            inicio = time.perf_counter()

            respuesta = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout,
            )

            tiempo_ejecucion = time.perf_counter() - inicio

            respuesta = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            respuesta.raise_for_status()
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"No se puede conectar con Ollama en {self.base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Ollama ha tardado demasiado en responder"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama ha devuelto el error HTTP "
                f"{exc.response.status_code}: {exc.response.text}"
            ) from exc

        try:
            datos = respuesta.json()

            if datos.get("done_reason") == "length":
                raise ProviderError(
                    "La respuesta ha superado el límite máximo "
                    "de longitud configurado"
                )

            contenido_json = datos["message"]["content"]
            contenido_estructurado = json.loads(contenido_json)

            respuesta_final = {
                "respuesta": contenido_estructurado["respuesta"].strip(),
                "tiempo_ejecución_segundos": round(
                    tiempo_ejecucion,
                    3,
                ),
            }

            contenido = json.dumps(
                respuesta_final,
                ensure_ascii=False,
                indent=2,
            )
        except ProviderError:
            raise

        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                "La respuesta de Ollama no tiene el formato esperado"
            ) from exc

        if not respuesta_final["respuesta"]:
            raise ProviderError(
                "Ollama ha devuelto una respuesta vacía"
            )

        return contenido