import unicodedata

from agente_familia.src.tools import (
    esta_hogar_vacio,
    generar_informe_familia,
    generar_informe_localizacion,
    generar_informe_anomalias,
    generar_informe_persona,
    avisar_anomalias_familia,
)
from agente_familia.src.events import detectar_llegada_mari_a_casa

ALIAS_PERSONAS = {
    "jose": "José",
    "pepe": "José",
    "mari": "Mari",
    "mama": "Mari",
    "jessica": "Jessica",
    "jessi": "Jessica",
    "javi": "Javi",
}

def normalizar(texto: str) -> str:
    texto = texto.lower().strip()

    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

    return texto


def contiene_alguna(texto: str, palabras: list[str]) -> bool:
    return any(palabra in texto for palabra in palabras)


def responder_local(pregunta: str) -> str:
    p = normalizar(pregunta)

    persona = buscar_persona_en_pregunta(p)

    if persona and contiene_alguna(
        p,
        ["donde esta", "donde se localiza", "localiza", "ubicacion", "direccion"]
    ):
        return generar_informe_persona(persona)
    # Llegada de Mari
    if "mari" in p and contiene_alguna(p, ["llega", "llegado", "vuelve", "vuelto"]):
        return detectar_llegada_mari_a_casa()

    # Anomalías
    if contiene_alguna(p, ["anomalia", "anomalias", "raro", "problema", "fallo"]):
        return generar_informe_anomalias()

    # Localización geográfica
    if contiene_alguna(p, ["localizan", "localizacion", "direccion", "calle", "ubicacion exacta"]):
        return generar_informe_localizacion()

    # Casa Jessi vacía
    if "casa jessi" in p and contiene_alguna(p, ["vacia", "vacio", "hay alguien", "ocupada"]):
        resultado = esta_hogar_vacio("Casa Jessi")
        return formatear_hogar(resultado)

    # Casa vacía
    if "casa" in p and contiene_alguna(p, ["vacia", "vacio", "hay alguien", "ocupada"]):
        resultado = esta_hogar_vacio("Casa")
        return formatear_hogar(resultado)

    # Estado general familia
    if contiene_alguna(p, ["familia", "cada uno", "donde estan", "donde esta", "situacion"]):
        return generar_informe_familia()

    if contiene_alguna(p, ["avisa anomalias", "avisar anomalias", "notifica anomalias", "notificar anomalias"]):
        return avisar_anomalias_familia()

    return (
        "No he entendido bien la pregunta.\n"
        "Puedes preguntarme, por ejemplo:\n"
        "- ¿Dónde está la familia?\n"
        "- ¿Dónde se localizan las personas?\n"
        "- ¿Está Casa vacía?\n"
        "- ¿Está Casa Jessi vacía?\n"
        "- ¿Hay anomalías?\n"
        "- ¿Ha llegado Mari?"
    )


def formatear_hogar(resultado: dict) -> str:
    hogar = resultado["hogar"]

    if resultado["vacio"]:
        return f"{hogar} está vacía."

    presentes = ", ".join(resultado["presentes"])
    return f"{hogar} no está vacía. Están: {presentes}."

def buscar_persona_en_pregunta(texto: str) -> str | None:
    for alias, nombre in ALIAS_PERSONAS.items():
        if alias in texto:
            return nombre

    return None