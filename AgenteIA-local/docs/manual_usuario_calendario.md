# Calendario familiar desde Telegram

## Finalidad

Agente Telegram permite consultar y añadir eventos al calendario compartido
**Familia Millan Romero** desde mensajes de texto o notas de voz.

El calendario oficial continúa almacenado en Google Calendar. El agente se
comunica con él a través de Home Assistant, por lo que estas operaciones no
utilizan un modelo de inteligencia artificial ni consumen tokens.

## Consultar el calendario

Se puede preguntar con lenguaje natural:

- `¿Qué tenemos hoy en el calendario?`
- `¿Qué tenemos mañana?`
- `¿Qué hay esta semana?`
- `Muéstrame el calendario de los próximos 14 días.`

También están disponibles estos comandos:

- `/agenda`: muestra los próximos siete días.
- `/agenda 14`: muestra los próximos catorce días.

Las consultas están limitadas a un máximo de 31 días para ofrecer respuestas
rápidas y fáciles de leer en Telegram.

## Crear un evento mediante texto

El mensaje debe incluir como mínimo el título, el día y la hora:

`Añade al calendario familiar Dentista mañana a las 18:00.`

Si no se indica duración, el agente asigna una hora. Para especificarla:

`Añade al calendario familiar Dentista mañana a las 18:00 durante 45 minutos.`

También se puede indicar el lugar:

`Añade al calendario familiar Dentista mañana a las 18:00 durante 45 minutos en Clínica X.`

Como alternativa se puede utilizar el comando:

`/evento Dentista mañana a las 18:00 durante 45 minutos en Clínica X`

## Fechas y horas admitidas

El agente reconoce:

- `hoy`
- `mañana`
- `pasado mañana`
- Fechas como `20/09` y `20/09/2026`
- Horas como `19`, `19 horas`, `19:30` y `19:30 horas`
- Duraciones expresadas en minutos u horas

Cuando se escribe una fecha sin año que ya ha pasado, el agente interpreta que
corresponde al año siguiente.

## Crear un evento mediante audio

1. Envía la nota de voz a Agente Telegram.
2. Revisa la transcripción mostrada.
3. Si es correcta, pulsa o envía `/confirmar_audio`.
4. Si necesita cambios, copia la transcripción y envíala como
   `/corregido <texto corregido>`.
5. Revisa la vista previa del evento.
6. Pulsa **Confirmar** para guardarlo o **Cancelar** para descartarlo.

Expresiones naturales como `a las 19 horas` son válidas y equivalen a
`a las 19:00`.

## Confirmación obligatoria

El agente nunca crea un evento al recibir la primera frase. Antes muestra una
vista previa con:

- Título
- Fecha
- Hora inicial y final
- Lugar, si se ha indicado
- Calendario de destino

Solo el botón **Confirmar** envía el evento a Home Assistant y Google Calendar.
El botón **Cancelar** descarta el borrador sin modificar el calendario.

## Sincronización

Después de confirmar, el evento puede tardar unos segundos en aparecer en
Google Calendar o en el panel de Home Assistant. No debe enviarse de nuevo
durante ese intervalo, pues podría producirse un duplicado.

Si existen dudas, puede comprobarse con:

`/agenda`

## Coste mostrado en Telegram

Las consultas y altas del calendario muestran en el pie:

- Modelo: No aplica
- Proveedor: Home Assistant + Google Calendar
- Tokens: 0 entrada + 0 salida
- Coste de tokens: US$0,000000

La transcripción de una nota de voz se realiza localmente con faster-whisper y
tampoco consume tokens del modelo.

## Limitaciones actuales

- Todos los eventos se consultan o crean en **Familia Millan Romero**.
- El agente todavía no modifica ni elimina eventos existentes.
- Las repeticiones semanales o mensuales deben configurarse actualmente en
  Google Calendar.
- Si faltan el día o la hora, el agente no crea el borrador y solicita una frase
  más precisa.

## Problemas frecuentes

### El evento no aparece inmediatamente

Espera unos segundos y consulta `/agenda`. Google Calendar y Home Assistant
pueden tardar brevemente en sincronizarse.

### La transcripción no reconoce bien la hora

Utiliza `/corregido` y escribe la hora como `19:00` o `19 horas`.

### El agente pide título, día y hora

Repite el mensaje siguiendo este modelo:

`Añade al calendario familiar <título> mañana a las <hora> durante <duración>.`

### No quiero guardar el evento

Pulsa **Cancelar** en la vista previa. El calendario no se modificará.
