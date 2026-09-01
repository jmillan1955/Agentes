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

- Recepción de notas de voz.
- Descarga temporal de audio OGG/Opus.
- Lectura de duración y tamaño.
- Eliminación automática del archivo temporal.

- Transcripción local de notas de voz con `faster-whisper`.
- Modelo Whisper `small`.
- Ejecución por CPU con cuantización `int8`.
- Idioma de transcripción configurado en español.
- Eliminación del audio después de transcribirlo.

## Próxima fase

## Próxima fase

- Enviar el texto transcrito a Ollama.
- Utilizar el texto como prompt para el modelo local.
- Devolver por Telegram la respuesta del modelo.

## Estructura

```text
agente_telegram/
├── .env
├── .env.example
├── guardar_token.py
├── main.py
├── README.md
└── requirements.txt