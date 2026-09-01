import os
import queue
from dataclasses import dataclass

from dotenv import load_dotenv
from pynput import keyboard

from capture.screen_capture import ScreenCapture
from pipeline.analyze_image import analyze_image


SUPPORTED_MODULES = {
    "spin_and_go": "Spin & Go",
}


@dataclass(frozen=True)
class AppConfig:
    agent_name: str
    version: str
    poker_variant: str
    module: str
    mode: str
    log_level: str


def load_config() -> AppConfig:
    load_dotenv()

    module = os.getenv(
        "DEFAULT_MODULE",
        "spin_and_go",
    ).strip().lower()

    if module not in SUPPORTED_MODULES:
        raise ValueError(
            f"Módulo no soportado: '{module}'. "
            f"Disponibles: "
            f"{', '.join(SUPPORTED_MODULES)}"
        )

    return AppConfig(
        agent_name=os.getenv(
            "AGENT_NAME",
            "agente_poker",
        ),

        version=os.getenv(
            "APP_VERSION",
            "0.1.0",
        ),

        poker_variant=os.getenv(
            "POKER_VARIANT",
            "texas_holdem",
        ),

        module=module,

        mode=os.getenv(
            "APP_MODE",
            "study",
        ),

        log_level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ),
    )


def print_startup(
    config: AppConfig,
) -> None:

    module_name = (
        SUPPORTED_MODULES[
            config.module
        ]
    )

    print()
    print("=" * 60)
    print(
        f"  {config.agent_name.upper()} "
        f"v{config.version}"
    )
    print("=" * 60)

    print(
        f"  Juego:          "
        f"{config.poker_variant}"
    )

    print(
        f"  Módulo activo:  "
        f"{module_name}"
    )

    print(
        f"  Modo:           "
        f"{config.mode}"
    )

    print(
        "  Hand Reader:    activo"
    )

    print(
        "  Captura F8:     activa"
    )

    print(
        "  GTO Engine:     pendiente"
    )

    print("=" * 60)

    print()
    print(
        "Pulsa F8 para capturar y analizar la mesa."
    )

    print(
        "Pulsa ESC para cerrar agente_poker."
    )

    print()


def main():

    config = load_config()

    print_startup(
        config
    )

    screen_capture = (
        ScreenCapture()
    )

    events = queue.Queue(
        maxsize=1
    )

    running = True

    # --------------------------------------------------
    # HOTKEY LISTENER
    # --------------------------------------------------

    def on_release(key):

        nonlocal running

        if key == keyboard.Key.f8:

            try:
                events.put_nowait(
                    "capture"
                )

                print()
                print(
                    "[F8] Captura solicitada."
                )

            except queue.Full:

                print(
                    "[F8] Ya hay una captura "
                    "pendiente."
                )

        elif key == keyboard.Key.esc:

            running = False

            try:
                events.put_nowait(
                    "exit"
                )
            except queue.Full:
                pass

            return False

    listener = keyboard.Listener(
        on_release=on_release
    )

    listener.start()

    # --------------------------------------------------
    # EVENT LOOP
    # --------------------------------------------------

    while running:

        event = events.get()

        if event == "exit":
            break

        if event != "capture":
            continue

        try:

            print()
            print(
                "[Capture] Capturando mesa..."
            )

            image_path = (
                screen_capture.capture()
            )

            print(
                f"[Capture] Imagen: "
                f"{image_path}"
            )

            print()
            print(
                "[Pipeline] Analizando..."
            )

            analyze_image(
                str(image_path)
            )

            print()
            print(
                "Listo. Pulsa F8 "
                "para analizar otra mano."
            )

        except Exception as exc:

            print()
            print(
                "[ERROR]"
            )

            print(
                str(exc)
            )

            print()
            print(
                "El agente continúa activo."
            )

    listener.stop()

    print()
    print(
        "AGENTE_POKER finalizado."
    )
    print()


if __name__ == "__main__":
    main()