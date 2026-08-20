# Agente Telegram

Bot de Telegram que recibe mensajes escritos y notas de voz para utilizarlos como entrada de un agente de inteligencia artificial.

## Estado actual

Primera fase completada:

- Bot creado con BotFather.
- Conexión mediante la API de Telegram.
- Token almacenado en un archivo `.env`.
- Token excluido del repositorio Git.
- Comando `/start`.
- Comando `/mi_id`.
- Recepción de mensajes escritos.
- Respuesta de prueba.
- Acceso restringido al usuario autorizado.
- Registros configurados para no mostrar el token.

## Estructura

```text
agente_telegram/
├── .env
├── .env.example
├── guardar_token.py
├── main.py
├── README.md
└── requirements.txt