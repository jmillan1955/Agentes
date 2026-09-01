import base64
import mimetypes
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from ollama import Client as OllamaClient
from openai import OpenAI

from models.raw_observation import RawTableObservation


HAND_READER_PROMPT = """
Analiza exclusivamente la captura de una mesa de Texas Hold'em.

Tu función es actuar como lector visual de la mesa.

NO debes:
- recomendar acciones;
- hacer análisis GTO;
- calcular stacks en BB;
- usar estadísticas del HUD para inferir stacks;
- inventar datos que no sean visibles.

Debes extraer únicamente lo observable en la imagen:

- número de jugadores visibles en la mesa;
- small blind;
- big blind;
- bote visible;
- jugadores y ubicación visual;
- stack visible detrás de cada jugador;
- fichas comprometidas/apostadas delante de cada jugador;
- cartas visibles de Hero;
- jugador con dealer button;
- quién es Hero;
- board, si existe.

REGLAS IMPORTANTES

1. Si un dato no se puede leer con suficiente seguridad, usa null.
2. No confundas el stack visible detrás del jugador con las fichas
   que ya tiene comprometidas en el bote.
3. No sumes ciegas o apuestas al stack visible.
4. Hero normalmente es el jugador cuyas cartas están visibles.
5. Ignora nombres de usuario y estadísticas HUD.
6. Ignora VPIP, PFR, número de manos y cualquier estadística.
7. No interpretes estrategia.
8. No conviertas cantidades a big blinds.
9. Añade a uncertainties cualquier dato que sea dudoso.

FORMATO DE CARTAS

Ac Ad Ah As
Kc Kd Kh Ks
Qc Qd Qh Qs
Jc Jd Jh Js
Tc Td Th Ts
...

Palos:
c = clubs
d = diamonds
h = hearts
s = spades

SEATS

Usa una de estas etiquetas visuales:

top_left
top_center
top_right
bottom_left
bottom
bottom_right
"""


def image_to_data_url(image_path: Path) -> str:
    """
    Convierte una imagen local en una data URL para OpenAI.
    """

    mime_type, _ = mimetypes.guess_type(image_path)

    if mime_type is None:
        mime_type = "image/png"

    encoded = base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    return (
        f"data:{mime_type};base64,{encoded}"
    )


class HandReader:

    def __init__(self):
        load_dotenv()
        self.last_elapsed_seconds = None
        self.provider = os.getenv(
            "VISION_PROVIDER",
            "ollama",
        ).strip().lower()

        self.timeout = float(
            os.getenv(
                "VISION_TIMEOUT_SECONDS",
                "120",
            )
        )

        if self.provider == "openai":
            self._configure_openai()

        elif self.provider == "ollama":
            self._configure_ollama()

        else:
            raise ValueError(
                f"VISION_PROVIDER no soportado: "
                f"'{self.provider}'. "
                f"Usa 'openai' u 'ollama'."
            )

    # --------------------------------------------------
    # CONFIGURACIÓN
    # --------------------------------------------------

    def _configure_openai(self):

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY no está configurada."
            )

        self.model = os.getenv(
            "OPENAI_VISION_MODEL",
            "gpt-5.6-luna",
        )

        self.image_detail = os.getenv(
            "OPENAI_IMAGE_DETAIL",
            "high",
        )

        self.client = OpenAI(
            api_key=api_key,
            timeout=self.timeout,
        )

    def _configure_ollama(self):

        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        )

        self.model = os.getenv(
            "OLLAMA_VISION_MODEL",
            "qwen3-vl:4b",
        )

        self.client = OllamaClient(
            host=self.base_url,
            timeout=self.timeout,
        )

    # --------------------------------------------------
    # INTERFAZ PÚBLICA
    # --------------------------------------------------

    def read_image(
        self,
        image_path: str | Path,
    ) -> RawTableObservation:

        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(
                f"No existe la imagen: "
                f"{image_path}"
            )

        print()
        print(
            f"[HandReader] Proveedor: "
            f"{self.provider}"
        )

        print(
            f"[HandReader] Modelo: "
            f"{self.model}"
        )

        print(
            f"[HandReader] Imagen: "
            f"{image_path}"
        )

        print(
            "[HandReader] Analizando..."
        )

        start = time.perf_counter()

        if self.provider == "openai":
            observation = self._read_openai(
                image_path
            )

        else:
            observation = self._read_ollama(
                image_path
            )

        elapsed = time.perf_counter() - start
        self.last_elapsed_seconds = elapsed
        

        print(
            f"[HandReader] Completado en "
            f"{elapsed:.2f} s"
        )

        print(
            "[HandReader] "
            "RAW_OBSERVATION válido."
        )

        print()

        return observation

    # --------------------------------------------------
    # OPENAI
    # --------------------------------------------------

    def _read_openai(
        self,
        image_path: Path,
    ) -> RawTableObservation:

        data_url = image_to_data_url(
            image_path
        )

        response = (
            self.client.responses.parse(
                model=self.model,

                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type":
                                    "input_text",
                                "text":
                                    HAND_READER_PROMPT,
                            },
                            {
                                "type":
                                    "input_image",
                                "image_url":
                                    data_url,
                                "detail":
                                    self.image_detail,
                            },
                        ],
                    }
                ],

                text_format=(
                    RawTableObservation
                ),
            )
        )

        observation = (
            response.output_parsed
        )

        if observation is None:
            raise RuntimeError(
                "OpenAI respondió, pero "
                "no generó un "
                "RAW_OBSERVATION válido."
            )

        usage = response.usage

        if usage is not None:
            print(
                f"[OpenAI] Input tokens:  "
                f"{usage.input_tokens}"
            )

            print(
                f"[OpenAI] Output tokens: "
                f"{usage.output_tokens}"
            )

            print(
                f"[OpenAI] Total tokens:  "
                f"{usage.total_tokens}"
            )

        return observation

    # --------------------------------------------------
    # OLLAMA
    # --------------------------------------------------

    def _read_ollama(
        self,
        image_path: Path,
    ) -> RawTableObservation:

        image_bytes = (
            image_path.read_bytes()
        )

        response = self.client.chat(
            model=self.model,

            messages=[
                {
                    "role": "user",
                    "content":
                        HAND_READER_PROMPT,
                    "images": [
                        image_bytes
                    ],
                }
            ],

            format=(
                RawTableObservation
                .model_json_schema()
            ),

            options={
                "temperature": 0,
            },
        )

        content = (
            response.message.content
        )

        if not content:
            raise RuntimeError(
                "Ollama devolvió "
                "una respuesta vacía."
            )

        observation = (
            RawTableObservation
            .model_validate_json(content)
        )

        prompt_tokens = getattr(
            response,
            "prompt_eval_count",
            None,
        )

        output_tokens = getattr(
            response,
            "eval_count",
            None,
        )

        if prompt_tokens is not None:
            print(
                f"[Ollama] Input tokens:  "
                f"{prompt_tokens}"
            )

        if output_tokens is not None:
            print(
                f"[Ollama] Output tokens: "
                f"{output_tokens}"
            )

        return observation


def main():

    if len(sys.argv) != 2:
        print(
            "Uso:\n"
            "python -m vision.hand_reader "
            "test_images\\test_001.png"
        )

        raise SystemExit(1)

    reader = HandReader()

    observation = reader.read_image(
        sys.argv[1]
    )

    print(
        observation.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()