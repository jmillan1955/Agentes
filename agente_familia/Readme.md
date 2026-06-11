# Uso de `local_ai` en Agente Familia

## Objetivo

`local_ai.py` es la capa de inteligencia local del Agente Familia.

No usa OpenAI ni ningún servicio externo. Su función es interpretar preguntas en lenguaje natural mediante reglas, alias y palabras clave, y decidir qué herramienta interna debe ejecutar.

---

# Endpoint recomendado

```text
POST /preguntar_local
```

Ejemplo:

```json
{
  "pregunta": "¿Dónde está Pepe?"
}
```

Requiere cabecera:

```text
x-api-key: CLAVE_DEL_AGENTE
```

---

# Qué hace `local_ai`

Flujo interno:

```text
Pregunta del usuario
↓
normalizar texto
↓
detectar alias de personas
↓
detectar intención
↓
ejecutar herramienta
↓
devolver respuesta
```

---

# Personas reconocidas

## José / Pepe

Preguntas que reconocen a José:

```text
¿Dónde está José?
¿Dónde está Pepe?
¿Dónde se localiza Pepe?
¿Cuál es la dirección de José?
```

Alias soportados:

```text
jose
pepe
```

---

## Mari

Preguntas que reconocen a Mari:

```text
¿Dónde está Mari?
¿Dónde está mamá?
¿Dónde se localiza Mari?
¿Cuál es la dirección de mamá?
```

Alias soportados:

```text
mari
mama
```

---

## Jessica

Preguntas que reconocen a Jessica:

```text
¿Dónde está Jessica?
¿Dónde está Jessi?
¿Dónde se localiza Jessica?
```

Alias soportados:

```text
jessica
jessi
```

---

## Javi

Preguntas que reconocen a Javi:

```text
¿Dónde está Javi?
¿Dónde se localiza Javi?
```

Alias soportados:

```text
javi
```

---

# Preguntas contempladas

## Estado general de la familia

```text
¿Dónde está la familia?
¿Dónde está cada uno?
¿Dónde están todos?
¿Cómo está la familia?
¿Cuál es la situación de la familia?
```

Herramienta usada:

```text
generar_informe_familia()
```

---

## Localización geográfica

```text
¿Dónde se localizan las personas?
¿Dónde se localiza la familia?
Dime la localización de todos
Dime la dirección de las personas
Dime la calle de cada uno
```

Herramienta usada:

```text
generar_informe_localizacion()
```

---

## Persona concreta

```text
¿Dónde está Pepe?
¿Dónde está José?
¿Dónde está Mari?
¿Dónde está mamá?
¿Dónde está Jessica?
¿Dónde está Jessi?
¿Dónde está Javi?
```

Herramienta usada:

```text
generar_informe_persona(nombre)
```

---

## Dirección o ubicación exacta de una persona

```text
¿Dónde se localiza Pepe?
¿Cuál es la dirección de Mari?
¿En qué calle está Jessica?
¿Dónde se ubica Javi?
```

Herramienta usada:

```text
generar_informe_persona(nombre)
```

---

## Casa vacía u ocupada

```text
¿Está Casa vacía?
¿Hay alguien en Casa?
¿Está ocupada Casa?
```

Herramienta usada:

```text
esta_hogar_vacio("Casa")
```

---

## Casa Jessi vacía u ocupada

```text
¿Está Casa Jessi vacía?
¿Hay alguien en Casa Jessi?
¿Está ocupada Casa Jessi?
```

Herramienta usada:

```text
esta_hogar_vacio("Casa Jessi")
```

---

## Anomalías

```text
¿Hay anomalías?
¿Hay anomalias?
¿Hay algo raro?
¿Hay algún problema?
¿Hay algún fallo?
¿Está todo bien?
```

Herramienta usada:

```text
generar_informe_anomalias()
```

---

## Llegada de Mari

```text
¿Ha llegado Mari?
¿Mari llega a casa?
¿Ha vuelto Mari?
¿Mamá ha llegado?
¿Mamá ha vuelto?
```

Herramienta usada:

```text
detectar_llegada_mari_a_casa()
```

---

# Preguntas no contempladas todavía

Estas preguntas todavía no están implementadas o pueden responder de forma incompleta.

## Historial

```text
¿A qué hora llegó Mari?
¿Cuándo salió Pepe?
¿Cuánto tiempo lleva Javi en Casa Jessi?
¿Cuándo estuvo Jessica fuera?
```

Motivo:

```text
Todavía no se consulta el historial de Home Assistant.
```

---

## Comparaciones temporales

```text
¿Quién llegó primero?
¿Quién salió más tarde?
¿Cuánto tiempo estuvo Mari fuera?
```

Motivo:

```text
Se necesita memoria histórica o consulta al historial de HA.
```

---

## Suscripciones

```text
Avísame cuando Mari llegue a casa
Avisa a Jessica cuando mamá llegue
Avísame si Casa se queda vacía
```

Motivo:

```text
Existe detección de eventos, pero aún no está implementado el sistema de suscripciones persistentes.
```

---

## Acciones reales

```text
Manda un mensaje a Jessica
Notifica a Javi
Activa la alarma
Abre la puerta
```

Motivo:

```text
La IA local actual es de consulta y análisis. No ejecuta acciones reales salvo las herramientas ya programadas.
```

---

## Preguntas ambiguas

```text
¿Está todo bien?
¿Qué pasa?
¿Cómo va todo?
```

Estado actual:

```text
Pueden mapearse a anomalías o situación general, pero todavía conviene mejorar la interpretación.
```

---

# Reglas importantes

## 1. Las reglas específicas van antes que las generales

Ejemplo:

```text
¿Dónde está Pepe?
```

Debe evaluarse antes que:

```text
¿Dónde está la familia?
```

porque si no, la frase `dónde está` puede activar el informe general.

Orden recomendado:

```text
1. Llegadas/eventos
2. Anomalías
3. Persona concreta
4. Localización geográfica
5. Casa Jessi
6. Casa
7. Familia general
8. Respuesta no entendida
```

---

## 2. Mantener alias separados del código de herramientas

Los alias deben vivir en `local_ai.py` o en un futuro archivo de configuración.

Ejemplo:

```python
ALIAS_PERSONAS = {
    "jose": "José",
    "pepe": "José",
    "mari": "Mari",
    "mama": "Mari",
    "jessica": "Jessica",
    "jessi": "Jessica",
    "javi": "Javi",
}
```

---

## 3. No mezclar IA local con acciones peligrosas

Por ahora `local_ai` solo debe:

```text
leer
analizar
informar
```

No debe:

```text
abrir puertas
activar alarmas
modificar configuraciones
```

---

# Mejoras futuras

## 1. Historial

Añadir consultas a Home Assistant para responder:

```text
¿Cuándo llegó Mari?
¿Cuándo salió Pepe?
```

---

## 2. Suscripciones

Permitir frases como:

```text
Avísame cuando mamá llegue a casa
```

y guardar:

```json
{
  "avisar_a": "Jessica",
  "persona": "Mari",
  "evento": "llegada",
  "zona": "Casa"
}
```

---

## 3. IA híbrida

Mantener `local_ai` como primera capa rápida y gratuita.

Si no entiende una pregunta, pasarla a:

```text
/preguntar_ia
```

cuando haya cuota disponible de OpenAI.

---

## 4. Agente Core

En el futuro, el Agente Core podrá decidir si una pregunta corresponde a:

```text
Agente Familia
Agente Aerotermia
Agente Placas
Agente Seguridad
```

---

# Estado actual

`local_ai` ya permite una interacción mucho más natural sin coste externo.

No es un LLM, pero sí es una capa de inteligencia local útil:

```text
lenguaje natural limitado
+
alias
+
intenciones
+
herramientas reales
```

Esto permite avanzar sin depender de cuota de OpenAI.
