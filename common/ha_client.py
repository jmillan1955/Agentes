import os
import requests
from dotenv import load_dotenv


load_dotenv()


class HomeAssistantClient:
    def __init__(self):
        self.base_url = os.getenv("HA_URL")
        self.token = os.getenv("HA_TOKEN")

        if not self.base_url:
            raise ValueError("Falta HA_URL en el archivo .env")

        if not self.token:
            raise ValueError("Falta HA_TOKEN en el archivo .env")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get_states(self) -> list[dict]:
        url = f"{self.base_url}/api/states"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=10,
        )

        response.raise_for_status()
        return response.json()

    def get_state(self, entity_id: str) -> dict:
        url = f"{self.base_url}/api/states/{entity_id}"

        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()

        return response.json()
    
    def call_service(self, domain: str, service: str, data: dict | None = None) -> dict:
        url = f"{self.base_url}/api/services/{domain}/{service}"

        response = requests.post(
            url,
            headers=self.headers,
            json=data or {},
            timeout=10,
        )

        response.raise_for_status()
        return response.json()
    
    def leer_zonas():
        ha = HomeAssistantClient()

        estados = ha.get_states()

        zonas = []

        for entidad in estados:
            if entidad["entity_id"].startswith("zone."):
                zonas.append({
                    "entity_id": entidad["entity_id"],
                    "nombre": entidad["attributes"].get("friendly_name"),
                    "latitud": entidad["attributes"].get("latitude"),
                    "longitud": entidad["attributes"].get("longitude"),
                    "radio": entidad["attributes"].get("radius"),
                })

        return zonas