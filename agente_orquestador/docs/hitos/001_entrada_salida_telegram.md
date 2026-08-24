# Hito 1: Entrada y salida mediante Telegram

**Fecha:** 23/08/2026  
**Proyecto:** Agente Orquestador  
**Versión:** 0.1.0  
**Estado:** Completado

## Objetivo

Construir el primer recorrido completo del Agente Orquestador:

```text
Telegram
→ IncomingMessage
→ Orchestrator
→ OutgoingMessage
→ Telegram
```

En este hito todavía no se utiliza ningún modelo de inteligencia artificial ni el almacén de contexto SQLite.

El objetivo es validar la separación entre el canal, los mensajes normalizados y el núcleo del orquestador.

## Bot de Telegram

Se creó un bot independiente:

```text
Nombre: Agente Orquestador Pepe Millan
Usuario: @AgenteOrquestadorPepeMillanBot
```

El nuevo bot permite desarrollar y probar el orquestador sin detener el bot de `agente_ia` y sin provocar conflictos de `getUpdates`.

## Seguridad

El token y el identificador autorizado se guardan en:

```text
agente_orquestador/.env
```

Variables:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
```

El archivo `.env` está excluido de Git mediante el `.gitignore` general.

El repositorio contiene solamente la plantilla:

```text
agente_orquestador/.env.example
```

El canal rechaza los mensajes procedentes de usuarios cuyo identificador no coincide con `TELEGRAM_ALLOWED_USER_ID`.

## Estructura creada

```text
agente_orquestador/
├── app/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── channels/
│   │   ├── __init__.py
│   │   └── telegram.py
│   └── models/
│       ├── __init__.py
│       ├── attachment.py
│       ├── messages.py
│       └── message_types.py
├── docs/
│   └── hitos/
│       └── 001_entrada_salida_telegram.md
├── tests/
│   ├── test_messages.py
│   ├── test_orchestrator.py
│   └── test_telegram_channel.py
├── .env
├── .env.example
├── config.py
├── main.py
├── pytest.ini
└── requirements.txt
```

## IncomingMessage

Todos los canales deberán convertir sus entradas al modelo común `IncomingMessage`.

Información principal:

- Identificador único del mensaje.
- Canal de procedencia.
- Usuario.
- Conversación.
- Tipo de contenido.
- Texto.
- Archivos adjuntos.
- Metadatos.
- Fecha de recepción.

Esto impide que el orquestador dependa directamente de Telegram.

## OutgoingMessage

El orquestador devuelve un `OutgoingMessage` independiente del formato externo.

La respuesta incluye:

- Identificador propio.
- Identificador de la petición original.
- Canal de salida.
- Conversación de destino.
- Tipo de contenido.
- Texto.
- Archivos adjuntos.
- Metadatos.
- Fecha de creación.

La relación entre petición y respuesta es:

```text
IncomingMessage.message_id
→ OutgoingMessage.correlation_id
```

## Attachment

El modelo `Attachment` representa cualquier contenido adjunto:

- Audio.
- Documento.
- Imagen.
- Otros tipos futuros.

Puede almacenar:

- Nombre.
- Tipo de contenido.
- Tipo MIME.
- Tamaño.
- Ruta temporal.
- Identificador remoto de Telegram.

En este hito todavía no se procesan archivos.

## Orquestador provisional

El orquestador recibe un `IncomingMessage` y devuelve un `OutgoingMessage`.

Su comportamiento provisional consiste en confirmar la recepción:

```text
He recibido correctamente tu mensaje:

<texto recibido>
```

La lógica no conoce objetos propios de Telegram.

## Canal Telegram

El adaptador Telegram es responsable de:

1. Recibir la actualización.
2. Comprobar el usuario autorizado.
3. Crear un `IncomingMessage`.
4. Entregarlo al orquestador.
5. Recibir el `OutgoingMessage`.
6. Enviar el texto a Telegram.

El canal divide las respuestas largas en fragmentos de un máximo de 4.000 caracteres.

## Configuración

Variables disponibles:

```dotenv
AGENT_NAME=Agente Orquestador Pepe Millan
AGENT_VERSION=0.1.0
AGENT_ENVIRONMENT=development

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
```

## Ejecución

Desde PowerShell:

```powershell
cd C:\Python_Proyectos\Agentes\agente_orquestador
python main.py
```

El inicio correcto muestra:

```text
Iniciando Agente Orquestador Pepe Millan versión 0.1.0
Iniciando canal Telegram
Control de acceso activado
Application started
```

La ejecución se detiene con:

```text
Ctrl+C
```

## Pruebas

Ejecución:

```powershell
pytest -v
```

Resultado:

```text
9 passed
```

Las pruebas verifican:

- Creación de mensajes de entrada.
- Creación de respuestas relacionadas.
- Rechazo de mensajes vacíos.
- Funcionamiento del orquestador provisional.
- Tratamiento de tipos todavía no soportados.
- Autorización del usuario de Telegram.
- Rechazo de usuarios no autorizados.
- Conversión de una actualización de Telegram a `IncomingMessage`.

## Prueba funcional

Se envió:

```text
/start
```

El bot confirmó su conexión.

Después se envió un mensaje de texto y se recibió la confirmación generada por el orquestador.

## Resultado

El Hito 1 queda completado satisfactoriamente.

El proyecto dispone de:

- Un canal Telegram independiente.
- Control de acceso.
- Contratos comunes de entrada y salida.
- Un orquestador desacoplado de Telegram.
- Pruebas automáticas.
- Un recorrido funcional completo.

## Próximo hito

Crear el almacén de contexto SQLite.

El primer objetivo será registrar:

- Sesiones.
- Mensajes de entrada.
- Mensajes de salida.
- Documentos del proyecto.
- Estado de sincronización.

SQLite se incorporará sin modificar el contrato ya establecido entre Telegram y el orquestador.
