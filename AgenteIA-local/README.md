# AgenteIA-local

Entrada y salida por Telegram para GPT-5.6 Terra, Luna y Sol mediante el SDK de
Codex para Python. Terra es el modelo predeterminado.

## Flujo actual

```text
Telegram texto ───────────────────────┐
                                     ├─> agente_telegram ─> agente_ia ─> Terra/Luna/Sol
Telegram audio ─> Whisper ─> revisión┘
```

Una nota de voz que empiece por **«barra»** puede ejecutar cualquier comando
registrado. Si Whisper omite esa palabra, también se acepta cuando la
transcripción empieza directamente por un comando inequívoco, como «evento
dentista mañana a las 12». Por ejemplo, «barra agenda» equivale a `/agenda`,
«barra estar» y «barra estart» a `/start`, y «barra aviso voz mensaje» a
`/aviso_voz mensaje`. Las frases conversacionales normales conservan el flujo
habitual de transcripción, revisión y confirmación.

Las peticiones de rutas de senderismo alrededor de Molina de Aragón producen
un mapa PNG con cartografía de OpenStreetMap y recorridos calculados por
BRouter. El bot lo envía como fotografía, con distancias y advertencia de
verificación del terreno.

Cada chat mantiene su contexto mientras el proceso está activo. `/nuevo` crea
una conversación limpia y `/modelo=terra|luna|sol` permite cambiar de modelo.
Terra y Luna usan la cuenta Free; Sol usa la cuenta Plus. El bot solo acepta el
usuario configurado y Codex se ejecuta con el sandbox de solo lectura.

Las conversaciones se guardan en SQLite, separadas por usuario de Telegram, y
se reconstruyen después de reiniciar el servicio. `/nuevo` pide un nombre y
también admite el atajo `/nuevo <nombre>`. `/conversaciones` muestra las últimas,
`/abrir <id>` recupera una y `/historial` enseña los mensajes recientes.
`TELEGRAM_ALLOWED_USER_IDS` admite varios identificadores separados por comas.

## Avisos al grupo de Home Assistant

El bot conversacional puede enviar pruebas al grupo mediante un segundo bot,
independiente del que recibe las consultas. El canal está bloqueado al grupo
configurado: los comandos no aceptan un `chat_id` y solo funcionan para los
usuarios incluidos en `TELEGRAM_ALLOWED_USER_IDS`.

Configura estas variables sin reutilizar el token del bot conversacional:

```text
TELEGRAM_NOTIFICATIONS_BOT_TOKEN=<token de @casa_sierra_nevada_30_bot>
TELEGRAM_NOTIFICATIONS_CHAT_ID=<identificador negativo del grupo>
TELEGRAM_NOTIFICATIONS_TTS_VOICE=es-ES-ElviraNeural
```

El nombre visible actual del segundo bot es **Bot Avisos Home Assistant**. Una
vez arrancado el agente, prueba desde el chat del bot conversacional:

```text
/aviso_texto Prueba escrita de Home Assistant
/aviso_voz Prueba de voz de Home Assistant
/aviso_ambos Prueba escrita y hablada de Home Assistant
```

`/aviso_texto` envía solo texto, `/aviso_voz` genera una nota de voz y
`/aviso_ambos` manda ambas cosas. La voz se genera con `edge-tts`, que requiere
acceso de red al servicio de voz de Microsoft. Los MP3 se crean en un directorio
temporal privado y se eliminan tanto si el envío termina bien como si falla.
El contenido que se transforma en voz se transmite a ese servicio externo.
Telegram no permite que un bot fuerce la reproducción automática del audio en
el teléfono del destinatario.

### Puente de eventos desde Home Assistant

AgenteIA-local puede escuchar un único evento de Home Assistant mediante una
conexión WebSocket **saliente**. No abre puertos ni requiere otro secreto:
reutiliza `HOME_ASSISTANT_TOKEN`. Para activarlo:

```text
HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED=true
```

También deben estar configurados `HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN` y
las variables `TELEGRAM_NOTIFICATIONS_*` anteriores. Si Home Assistant no está
disponible, el bot continúa funcionando y el puente reconecta con espera
progresiva. El evento admitido se llama exactamente `agenteia_notification` y
su carga solo puede contener:

- `titulo`: texto opcional de hasta 200 caracteres.
- `mensaje`: texto obligatorio, no vacío, de hasta 12.000 caracteres.
- `modo`: valor obligatorio `text`, `voice` o `both`.

Acción exacta para el bloque Telegram del script de Home Assistant:

```yaml
- event: agenteia_notification
  event_data:
    titulo: "Home Assistant"
    mensaje: "La puerta del garaje está abierta"
    modo: text
```

Para voz usa `modo: voice`; para texto y voz usa `modo: both`. Los eventos con
campos adicionales, tipos incorrectos, texto vacío, valores fuera de los
límites o modos distintos se ignoran. El token nunca se incluye en los logs.

El script `Notificaciones centralizadas` expone `modo_telegram` y mantiene
`text` como valor predeterminado para conservar la compatibilidad. Para usar
exclusivamente la ruta de Telegram:

```yaml
- action: script.notificaciones_centralizadas
  data:
    tipo: telegram
    titulo: "Home Assistant"
    mensaje: "La puerta del garaje está abierta"
    modo_telegram: both
```

El capítulo independiente para usuarios está en
[`docs/manual_usuario_calendario.md`](docs/manual_usuario_calendario.md).

El calendario compartido `Familia Millan Romero` se consulta a través de Home
Assistant, sin consumir tokens del modelo. Se puede usar `/agenda`,
`/agenda 14 días` o preguntas como `¿Qué tenemos mañana en el calendario?`.
También admite frases como `Añade al calendario familiar Dentista mañana a
las 18:00 durante 45 minutos en Clínica X` y el atajo `/evento`. El bot muestra
siempre una vista previa con botones Confirmar y Cancelar antes de crear el
evento. Tras confirmarlo, avisa de que la sincronización visual puede tardar
unos segundos. No modifica ni elimina eventos existentes.

Para activarlo, añade a `.env` la URL de Home Assistant, un token de larga
duración y el identificador de la entidad creada por la integración de Google
Calendar:

```text
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=
HOME_ASSISTANT_FAMILY_CALENDAR_ENTITY_ID=calendar.familia_millan_romero
HOME_ASSISTANT_SHOPPING_LIST_HOME=todo.casa
HOME_ASSISTANT_SHOPPING_LIST_JESSI=todo.casa_jessi
```

Las listas locales `Casa` y `Casa Jessi` se gestionan directamente mediante
Home Assistant, sin consumo de tokens. Se pueden consultar con `/lista casa` y
`/lista jessi`, añadir productos con `/compra casa leche y huevos` o mediante
frases naturales. Las operaciones de borrado requieren confirmación.

Consulta [`docs/manual_usuario_lista_compra.md`](docs/manual_usuario_lista_compra.md)
para ver todos los ejemplos disponibles.

## Configuración

1. Iniciar sesión una vez con `codex login`.
2. Copiar `.env.example` como `.env` y completar el token y el usuario.
3. Crear el entorno e instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecutar Telegram

```powershell
.\.venv\Scripts\python.exe .\main.py
```

## Prueba directa

```powershell
.\.venv\Scripts\python.exe .\prueba_luna.py "¿Qué diferencia hay entre masa y peso?"
```

Terra y Luna usan razonamiento `none`; Sol usa `medium` de forma predeterminada.

## Triaje de tareas

Las solicitudes directas o indirectas de trabajo (`crea`, `implementa`,
`corrige`, `quiero que...`, `podrias...`) ya no se contestan como una consulta
normal. El agente las clasifica, solicita solo los datos materiales que falten
y genera un prompt profesional junto con un plan estructurado. Las preguntas
conceptuales y el texto citado siguen la conversacion normal; los comandos
existentes se procesan antes del triaje.

El ciclo por Telegram es:

```text
solicitud -> aclaraciones, si hacen falta -> plan versionado -> aprobacion exacta
```

Comandos disponibles:

```text
/ver_plan [id_tarea]
/responder_tarea <id_tarea> <respuesta>
/aprobar_tarea <id_tarea> <version> <huella_sha256>
```

Solo los usuarios incluidos explicitamente en
`TELEGRAM_TASK_APPROVER_USER_IDS` pueden aprobar. La aprobacion registra la
version y la huella exactas del ultimo plan y nunca ejecuta cambios por si
sola. El modulo de ejecucion expone una puerta separada para integradores y
bloquea cualquier intento sin aprobacion vigente. Las tareas, aclaraciones,
versiones, aprobaciones y ejecuciones se conservan en la misma base SQLite con
claves de idempotencia para no duplicar trabajo al recibir de nuevo un mensaje.

El diseño, los estados y las garantías de seguridad se detallan en
[`docs/flujo_tareas.md`](docs/flujo_tareas.md).
