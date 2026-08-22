from app.documentation_service import (
    DocumentationService,
    RegistroAvance,
)


def crear_avance() -> RegistroAvance:
    return RegistroAvance(
        componente="Prueba automática",
        objetivo="Comprobar la generación de documentos Markdown.",
        archivos=["archivo_prueba.py"],
        pruebas=["Ejecución mediante pytest."],
        resultado="Completado correctamente",
        problemas_pendientes=[],
        proximo_paso="Continuar con el Agente IA.",
    )


def test_crea_documento_markdown(tmp_path):
    servicio = DocumentationService(tmp_path)

    documento = servicio.registrar(crear_avance())

    assert documento.exists()
    assert documento.suffix == ".md"

    contenido = documento.read_text(encoding="utf-8")

    assert "# Avance 001 — Prueba automática" in contenido
    assert "Comprobar la generación" in contenido
    assert "archivo_prueba.py" in contenido
    assert "Completado correctamente" in contenido


def test_incrementa_numeracion(tmp_path):
    servicio = DocumentationService(tmp_path)

    primero = servicio.registrar(crear_avance())
    segundo = servicio.registrar(crear_avance())

    assert "_001_" in primero.name
    assert "_002_" in segundo.name
    assert primero != segundo


def test_normaliza_nombre_del_componente(tmp_path):
    servicio = DocumentationService(tmp_path)

    avance = crear_avance()
    avance.componente = "Documentación automática"

    documento = servicio.registrar(avance)

    assert documento.name.endswith(
        "_documentacion_automatica.md"
    )