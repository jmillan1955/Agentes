import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.estado import estado_cocina, estado_lock


_tarea_temporizador: threading.Thread | None = None
_cancelar_temporizador = threading.Event()


def iniciar_temporizador(
    duracion_minutos: int,
    al_notificar: Callable[[str], None],
    al_finalizar: Callable[[], None],
) -> None:
    global _tarea_temporizador

    cancelar_temporizador()

    _cancelar_temporizador.clear()

    with estado_lock:
        estado_cocina["temporizador_activo"] = True
        estado_cocina["temporizador_fin"] = (
            datetime.now(timezone.utc) + timedelta(minutes=duracion_minutos)
        ).isoformat()

    _tarea_temporizador = threading.Thread(
        target=_ejecutar_temporizador,
        args=(
            duracion_minutos,
            al_notificar,
            al_finalizar,
        ),
        daemon=True,
    )
    _tarea_temporizador.start()


def _ejecutar_temporizador(
    duracion_minutos: int,
    al_notificar: Callable[[str], None],
    al_finalizar: Callable[[], None],
) -> None:
    fin_monotonic = time.monotonic() + duracion_minutos * 60

    siguiente_aviso = duracion_minutos - 2

    while siguiente_aviso > 0:
        instante_aviso = fin_monotonic - siguiente_aviso * 60
        espera = instante_aviso - time.monotonic()

        if espera > 0 and _cancelar_temporizador.wait(espera):
            return

        if _cancelar_temporizador.is_set():
            return

        if siguiente_aviso == 1:
            mensaje = "Queda 1 minuto."
        else:
            mensaje = f"Quedan {siguiente_aviso} minutos."

        al_notificar(mensaje)
        siguiente_aviso -= 2

    espera_final = fin_monotonic - time.monotonic()

    if espera_final > 0 and _cancelar_temporizador.wait(espera_final):
        return

    if _cancelar_temporizador.is_set():
        return

    with estado_lock:
        estado_cocina["temporizador_activo"] = False
        estado_cocina["temporizador_fin"] = None

    al_notificar("El tiempo ha terminado.")
    al_finalizar()


def cancelar_temporizador() -> None:
    global _tarea_temporizador

    _cancelar_temporizador.set()

    with estado_lock:
        estado_cocina["temporizador_activo"] = False
        estado_cocina["temporizador_fin"] = None

    _tarea_temporizador = None