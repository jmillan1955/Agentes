import os
from dotenv import load_dotenv
from openai import OpenAI

from agente_familia.src.agent import responder


load_dotenv()

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY no configurada"
        )

    return OpenAI(api_key=api_key)





def responder_con_ia(pregunta: str) -> str:
    respuesta_base = responder(pregunta)

    prompt = f"""
    Eres el Agente Familia.

    Tienes acceso a información real de Home Assistant,
    pero solo debes usar la respuesta técnica que se te proporciona.

    No inventes datos.
    No añadas ubicaciones, personas ni eventos que no aparezcan en la respuesta técnica.
    Responde en español, de forma clara, natural y breve.

    Pregunta del usuario:
    {pregunta}

    Respuesta técnica:
    {respuesta_base}
    """

    client = get_client()

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )

    return response.output_text   