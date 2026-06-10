from agente_familia.src.tools import (
    esta_hogar_vacio,
    generar_informe_familia,
    generar_informe_localizacion,
    generar_informe_anomalias,
    intentar_actualizar_ubicaciones,
)

from agente_familia.src.events import detectar_llegada_mari_a_casa

def responder(pregunta: str) -> str:
    pregunta = pregunta.lower()

    if "casa jessi" in pregunta and "vacía" in pregunta:
        resultado = esta_hogar_vacio("Casa Jessi")
        return formatear_hogar_vacio(resultado)

    if "casa" in pregunta and "vacía" in pregunta:
        resultado = esta_hogar_vacio("Casa")
        return formatear_hogar_vacio(resultado)

    if "localizan" in pregunta or "localización" in pregunta or "localizacion" in pregunta:
        return generar_informe_localizacion()

    if "familia" in pregunta or "dónde" in pregunta:
        return generar_informe_familia()

    if "anomalía" in pregunta or "anomalia" in pregunta or "anomalías" in pregunta or "anomalias" in pregunta:
        return generar_informe_anomalias()
    
    if "actualiza" in pregunta or "actualizar" in pregunta:
        return intentar_actualizar_ubicaciones()

    if "mari" in pregunta and "llega" in pregunta:
        return detectar_llegada_mari_a_casa()

    return "No sé responder todavía a esa pregunta."


def formatear_hogar_vacio(resultado: dict) -> str:
    hogar = resultado["hogar"]

    if resultado["vacio"]:
        return f"{hogar} está vacía."

    presentes = ", ".join(resultado["presentes"])
    return f"{hogar} no está vacía. Están: {presentes}."