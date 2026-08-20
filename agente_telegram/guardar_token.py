import re
import tkinter as tk
from pathlib import Path


def leer_portapapeles() -> str:
    ventana = tk.Tk()
    ventana.withdraw()

    try:
        contenido = ventana.clipboard_get().strip()
        ventana.clipboard_clear()
        ventana.update()
        return contenido
    finally:
        ventana.destroy()


def main() -> None:
    token = leer_portapapeles()

    patron_token = r"^\d+:[A-Za-z0-9_-]+$"

    if not re.fullmatch(patron_token, token):
        raise ValueError(
            "El portapapeles no contiene un token de Telegram válido"
        )

    ruta_env = Path(__file__).resolve().parent / ".env"

    ruta_env.write_text(
        f"TELEGRAM_BOT_TOKEN={token}\n",
        encoding="utf-8",
    )

    print("Token guardado correctamente en .env")
    print("El portapapeles ha sido vaciado")


if __name__ == "__main__":
    main()