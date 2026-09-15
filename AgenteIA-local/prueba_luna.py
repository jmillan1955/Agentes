from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from openai_codex import Codex, Sandbox


MODEL = "gpt-5.6-luna"
EFFORT = "low"
DEFAULT_QUESTION = "¿Cuál es la capital de Australia y por qué no es Sídney?"


def configure_windows_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueba mínima de GPT-5.6 Luna mediante el SDK de Codex."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=DEFAULT_QUESTION,
        help="Pregunta que se enviará a Luna sin modificarla.",
    )
    return parser.parse_args()


def find_luna(codex: Codex):
    for model in codex.models(include_hidden=True).data:
        if model.model == MODEL:
            return model
    raise RuntimeError(f"El modelo {MODEL} no está disponible para esta cuenta.")


def main() -> int:
    configure_windows_console()
    args = parse_args()
    project_dir = Path(__file__).resolve().parent

    with Codex() as codex:
        account_response = codex.account()
        account = account_response.account.root if account_response.account else None
        if getattr(account, "type", None) != "chatgpt":
            raise RuntimeError("Codex no está autenticado mediante una cuenta de ChatGPT.")

        luna = find_luna(codex)
        supported_efforts = {
            option.reasoning_effort.value
            for option in luna.supported_reasoning_efforts
        }
        if EFFORT not in supported_efforts:
            raise RuntimeError(
                f"{MODEL} no admite el esfuerzo solicitado: {EFFORT}."
            )

        thread = codex.thread_start(
            cwd=str(project_dir),
            ephemeral=True,
            model=MODEL,
            sandbox=Sandbox.read_only,
        )

        started = time.perf_counter()
        result = thread.run(
            args.question,
            effort=EFFORT,
            sandbox=Sandbox.read_only,
        )
        elapsed = time.perf_counter() - started

    print(f"Modelo: {MODEL}")
    print(f"Razonamiento: {EFFORT}")
    print(f"Tiempo: {elapsed:.2f} s")
    print("Respuesta:")
    print(result.final_response)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
