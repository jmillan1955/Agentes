from pynput import keyboard, mouse


mouse_controller = mouse.Controller()

top_left = None
bottom_right = None


def on_press(key):
    global top_left
    global bottom_right

    if key == keyboard.Key.f6:
        top_left = mouse_controller.position

        print(
            f"[F6] Esquina superior izquierda: "
            f"{top_left}"
        )

    elif key == keyboard.Key.f7:
        bottom_right = mouse_controller.position

        print(
            f"[F7] Esquina inferior derecha: "
            f"{bottom_right}"
        )

    elif key == keyboard.Key.esc:
        print("Calibración cancelada.")
        return False

    if (
        top_left is not None
        and bottom_right is not None
    ):
        return False


def main():
    print()
    print("=" * 60)
    print("CALIBRACIÓN DE CAPTURA")
    print("=" * 60)
    print()
    print(
        "1. Pon el ratón en la esquina SUPERIOR IZQUIERDA "
        "de la mesa y pulsa F6."
    )
    print(
        "2. Pon el ratón en la esquina INFERIOR DERECHA "
        "de la mesa y pulsa F7."
    )
    print()
    print("ESC cancela.")
    print()

    with keyboard.Listener(
        on_press=on_press
    ) as listener:
        listener.join()

    if (
        top_left is None
        or bottom_right is None
    ):
        return

    left = min(
        top_left[0],
        bottom_right[0],
    )

    top = min(
        top_left[1],
        bottom_right[1],
    )

    width = abs(
        bottom_right[0]
        - top_left[0]
    )

    height = abs(
        bottom_right[1]
        - top_left[1]
    )

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print()
    print(
        f"CAPTURE_LEFT={left}"
    )
    print(
        f"CAPTURE_TOP={top}"
    )
    print(
        f"CAPTURE_WIDTH={width}"
    )
    print(
        f"CAPTURE_HEIGHT={height}"
    )
    print()


if __name__ == "__main__":
    main()