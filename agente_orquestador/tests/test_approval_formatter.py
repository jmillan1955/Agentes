from types import SimpleNamespace

from app.approvals.formatter import (
    ApprovalFormatter,
)

def create_result(
    already_approved: bool = False,
):
    return SimpleNamespace(
        task=SimpleNamespace(
            id=3,
            target_project_name=(
                "puntuacion_padel"
            ),
        ),
        plan=SimpleNamespace(
            version=2,
        ),
        approval=SimpleNamespace(
            authorized_user_id=(
                "8288969559"
            ),
            created_at=(
                "2026-08-26T06:30:00.000Z"
            ),
        ),
        already_approved=(
            already_approved
        ),
    )


def test_formats_new_approval() -> None:
    text = ApprovalFormatter().format(
        create_result()
    )

    assert text.startswith(
        "PLAN APROBADO"
    )
    assert "Tarea: #3" in text
    assert (
        "Proyecto: puntuacion_padel"
        in text
    )
    assert (
        "Plan aprobado: version 2"
        in text
    )
    assert (
        "Usuario aprobador: 8288969559"
        in text
    )
    assert (
        "La autorizacion ha quedado "
        "registrada correctamente."
        in text
    )
    assert (
        "No se ha creado ni modificado "
        "codigo del proyecto."
        in text
    )


def test_formats_existing_approval() -> None:
    text = ApprovalFormatter().format(
        create_result(
            already_approved=True
        )
    )

    assert text.startswith(
        "PLAN YA APROBADO"
    )
    assert (
        "La tarea ya estaba "
        "autorizada anteriormente."
        in text
    )
    assert (
        "Se conserva la autorizacion "
        "original."
        in text
    )

def create_cancellation_result(
    already_cancelled: bool = False,
):
    return SimpleNamespace(
        task=SimpleNamespace(
            id=3,
            target_project_name=(
                "puntuacion_padel"
            ),
        ),
        plan=SimpleNamespace(
            version=7,
        ),
        cancelled_user_id=(
            "8288969559"
        ),
        already_cancelled=(
            already_cancelled
        ),
    )


def test_formats_new_cancellation() -> None:
    text = (
        ApprovalFormatter()
        .format_cancellation(
            create_cancellation_result()
        )
    )

    assert text.startswith(
        "TAREA APROBADA CANCELADA"
    )
    assert "Tarea: #3" in text
    assert (
        "Proyecto: puntuacion_padel"
        in text
    )
    assert (
        "Plan aprobado conservado: "
        "version 7"
        in text
    )
    assert (
        "Cancelada por: 8288969559"
        in text
    )
    assert (
        "La tarea aprobada ha sido "
        "cancelada correctamente."
        in text
    )
    assert (
        "La autorizacion se conserva "
        "como historial."
        in text
    )
    assert (
        "La tarea no podra iniciar "
        "su ejecucion."
        in text
    )
    assert (
        "No se ha creado ni modificado "
        "codigo del proyecto."
        in text
    )


def test_formats_existing_cancellation() -> None:
    text = (
        ApprovalFormatter()
        .format_cancellation(
            create_cancellation_result(
                already_cancelled=True
            )
        )
    )

    assert text.startswith(
        "TAREA YA CANCELADA"
    )
    assert (
        "La tarea ya estaba cancelada."
        in text
    )
    assert (
        "La autorizacion se conserva "
        "como historial."
        in text
    )
    assert (
        "La tarea no podra iniciar "
        "su ejecucion."
        in text
    )