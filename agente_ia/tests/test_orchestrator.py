from app.models import Peticion
from app.orchestrator import Orchestrator


def test_procesa_peticion_de_texto():
    orchestrator = Orchestrator()
    peticion = Peticion(
        contenido="Explica qué es un agente de IA"
    )

    respuesta = orchestrator.procesar(peticion)

    assert respuesta.correcto is True
    assert respuesta.peticion_id == peticion.id
    assert respuesta.herramienta == "respuesta_provisional"
    assert "Explica qué es un agente" in respuesta.contenido


def test_rechaza_peticion_vacia():
    orchestrator = Orchestrator()
    peticion = Peticion(contenido="   ")

    respuesta = orchestrator.procesar(peticion)

    assert respuesta.correcto is False
    assert respuesta.peticion_id == peticion.id
    assert "vacía" in respuesta.contenido


def test_muestra_ayuda():
    orchestrator = Orchestrator()
    peticion = Peticion(contenido="/ayuda")

    respuesta = orchestrator.procesar(peticion)

    assert respuesta.correcto is True
    assert respuesta.herramienta == "ayuda"
    assert "Capacidades actuales" in respuesta.contenido


from providers.base import ProviderError


class FakeProvider:
    def responder(self, texto: str) -> str:
        return f"Respuesta simulada para: {texto}"


class FailingProvider:
    def responder(self, texto: str) -> str:
        raise ProviderError("Proveedor no disponible")


def test_utiliza_proveedor_de_lenguaje():
    orchestrator = Orchestrator(
        language_provider=FakeProvider()
    )
    peticion = Peticion(contenido="Pregunta de prueba")

    respuesta = orchestrator.procesar(peticion)

    assert respuesta.correcto is True
    assert respuesta.herramienta == "ollama"
    assert respuesta.peticion_id == peticion.id
    assert respuesta.contenido == (
        "Respuesta simulada para: Pregunta de prueba"
    )


def test_controla_error_del_proveedor():
    orchestrator = Orchestrator(
        language_provider=FailingProvider()
    )
    peticion = Peticion(contenido="Pregunta de prueba")

    respuesta = orchestrator.procesar(peticion)

    assert respuesta.correcto is False
    assert respuesta.herramienta == "ollama"
    assert "Proveedor no disponible" in respuesta.contenido