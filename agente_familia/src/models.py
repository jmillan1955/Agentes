"""
Modelo de datos del agente familia
"""

PERSONAS = {
    "José": "person.jose",
    "Mari": "person.mari",
    "Jessica": "person.jessica",
    "Javi": "person.javi",
}

HOGARES = {
    "Casa": {
        "zona": "home",
        "personas": ["José", "Mari"],
        "latitud": 40.552348,
        "longitud": -3.9019597,
        "radio_metros": 200,
    },
    "Casa Jessi": {
        "zona": "Casa Jessi",
        "personas": ["Jessica", "Javi"],
    },
}

GEOCODED_SENSORS = {
    "José": "sensor.movil_pepe_geocoded_location",
    "Mari": "sensor.mari_carmen_geocoded_location",
    "Jessica": "sensor.iphone_de_jess_geocoded_location",
    "Javi": "sensor.javi_movil_geocoded_location",
}

SENSORES_ACCESO_CASA = {
    "Puerta principal": "binary_sensor.puerta_principal_contact",
    "Puerta garaje": "binary_sensor.puerta_garaje_contact",
}