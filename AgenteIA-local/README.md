# AgenteIA-local

Entrada y salida por Telegram para GPT-5.6 Terra, Luna y Sol mediante el SDK de
Codex para Python. Terra es el modelo predeterminado.

## Flujo actual

```text
Telegram texto ───────────────────────┐
                                     ├─> agente_telegram ─> agente_ia ─> Terra/Luna/Sol
Telegram audio ─> Whisper ─> revisión┘
```

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
```

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
El orquestador y los permisos de escritura se incorporarán en hitos posteriores.
