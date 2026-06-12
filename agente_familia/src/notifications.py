from common.ha_client import HomeAssistantClient


def notificar_familia(titulo: str, mensaje: str, personas: list[str] | None = None) -> str:
    ha = HomeAssistantClient()

    data = {
        "entity_id": "script.notificaciones_centralizadas",
        "variables": {
            "tipo": "familia",
            "titulo": titulo,
            "mensaje": mensaje,
            "personas": personas or [],
        },
    }

    ha.call_service("script", "turn_on", data)

    return "Notificación familia enviada."




def avisar_jessica(mensaje: str) -> str:
    """
    MVP: aviso simulado.
    Más adelante aquí llamaremos a Home Assistant:
    notify.mobile_app_iphone_de_jess
    """
    return f"AVISO PARA JESSICA: {mensaje}"