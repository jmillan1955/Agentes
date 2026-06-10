# Agentes

Proyecto de agentes de IA para la gestión inteligente del hogar.

## Agentes

- Agente Aerotermia
- Agente Placas Solares
- Agente Seguridad
- Agente Cámaras
- Agente Core

## Infraestructura

- Home Assistant
- ViCare
- Frigate
- Nuki
- Zigbee2MQTT
- Alexa




Estado de las viviendas
¿Está Casa vacía?

¿Está Casa Jessi vacía?
Estado de la familia
¿Dónde está la familia?

¿Dónde está cada uno?

Familia

¿Dónde?
Localización geográfica
¿Dónde se localizan las personas?

¿Dónde se localiza la familia?

Debería responder usando:

Calle
Ciudad
Provincia

en lugar de la zona.

Anomalías
¿Hay anomalías?

¿Hay anomalias?

Anomalías

Anomalias
Llegada de Mari
¿Mari llega a casa?

¿Ha llegado Mari?

¿Mari ha llegado a casa?

(según cómo hayas dejado la condición en agent.py)

Preguntas que todavía NO entiende

Ahora mismo NO debería responder correctamente:

¿Dónde está Mari?

¿Dónde está José?

¿Dónde está Jessica?

¿Dónde está Javi?
¿Quién está en Casa?

¿Quién está en Casa Jessi?
¿Quién está fuera?

¿Quién está fuera de casa?
¿Cuándo actualizó Mari?

¿Cuándo actualizó Javi?

¿Cuándo fue la última posición de Jessica?
¿Qué tracker utiliza Mari?

¿Qué móvil utiliza José?
Lo que yo desarrollaría mañana

Capacidad:

Información individual

Ejemplos:

¿Dónde está Mari?

Respuesta:

Mari está en Casa.

Localización:
Calle de la Sierra Nevada, 36
Las Rozas de Madrid, Madrid

Última actualización:
hace 2 horas.

Tracker:
device_tracker.mari_carmen
¿Dónde está Javi?

Respuesta:

Javi está en Casa Jessi.

Localización:
...
Lo que tenemos realmente

Si lo analizamos como arquitectura:

Agente Familia v0.1

✓ Memoria
✓ Herramientas
✓ Consulta Home Assistant
✓ Geolocalización
✓ Detección de anomalías
✓ Detección de llegada
✓ Despliegue Ubuntu
✓ Publicado en GitHub

Ya no estamos haciendo pruebas. Ya tenemos un agente operativo.

El siguiente salto importante será que el agente pueda responder sobre personas concretas y luego convertirlo en un servicio permanente (systemd) para que se quede funcionando 24x7 en Ubuntu.