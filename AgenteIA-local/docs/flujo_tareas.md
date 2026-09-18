# Flujo de construcción de tareas

Este documento describe el triaje incorporado a AgenteIA-local. Su objetivo es
separar una consulta conversacional de una petición de trabajo y asegurar que
ningún trabajo pueda ejecutarse sin aprobar de forma explícita la versión
vigente de su plan.

## Decisión de entrada

Cada mensaje que no haya sido consumido antes por un comando, calendario,
listas de compra o mapas se clasifica como uno de estos tipos:

- `command`: comienza por `/`; nunca se convierte en tarea.
- `query`: pregunta conceptual, explicación o conversación normal.
- `task`: acción directa o indirecta con confianza suficiente.
- `clarification`: posible acción cuyo sentido todavía es ambiguo.

El clasificador elimina primero bloques de código y texto entre comillas para
que ejemplos como `"crea un archivo"` no creen tareas. También da prioridad a
formas interrogativas (`cómo`, `qué`, `por qué`) y a peticiones de explicación.
Reconoce, entre otros, `construye`, `escribe`, `planifica`, `crea`, `implementa`,
`modifica` y `corrige`, además de formas indirectas como `necesito que`,
`podrías`, `encárgate de`, `vamos a` y `hay que`.

La decisión conserva la confianza, el proyecto reconocido y una ruta escrita
explícitamente. No inventa rutas a partir del nombre de un proyecto.

## Aclaraciones adaptativas

Antes de consultar al planificador se comprueba si faltan datos que cambiarían
materialmente el resultado. Por ejemplo:

- qué componente debe cambiar cuando la referencia es `esto` o `este bug`;
- en qué proyecto o ruta se hará un cambio de software;
- qué plataforma o tecnología debe usar una aplicación nueva.

Las respuestas se registran con `/responder_tarea`. Si todavía falta un dato
material, la tarea sigue en `pending_clarification`; el modelo no se invoca.

## Plan estructurado

El planificador debe devolver JSON válido con estos campos obligatorios:

```text
objective
professional_prompt
scope[]
technologies[]
phases[].name
phases[].objective
phases[].deliverables[]
tests[]
risks[]
exclusions[]
completion_criteria[]
```

La respuesta se analiza y valida antes de persistirla. Si no cumple el
contrato, se envía al modelo una petición de reparación con el error concreto.
Hay como máximo tres intentos; después la tarea queda en `planning_failed` y no
se crea un plan parcial.

Cada regeneración produce una versión nueva y marca la anterior como
`superseded`. La huella SHA-256 se calcula sobre el JSON canónico del plan.

## Aprobación y ejecución

`/aprobar_tarea <id> <version> <huella>` solo admite la última versión exacta.
El usuario debe estar incluido en `TELEGRAM_TASK_APPROVER_USER_IDS`, una lista
separada de los usuarios que pueden conversar con el bot.

La aprobación no ejecuta nada. La puerta de ejecución está expuesta como una
operación independiente para futuros integradores y exige que coincidan:

- tarea;
- identificador del plan;
- última versión;
- huella del contenido;
- registro de aprobación.

Sin esas cinco condiciones, se produce `ExecutionBlockedError` antes de llamar
al ejecutor. El adaptador de Telegram actual no conecta ningún ejecutor de
escritura.

## Persistencia e idempotencia

El flujo usa la misma base SQLite del historial y añade cinco tablas:

- `task_requests`;
- `task_clarifications`;
- `task_plans`;
- `task_approvals`;
- `task_executions`.

Los mensajes de Telegram forman claves idempotentes con chat e identificador de
mensaje. Repetir una solicitud, aclaración, aprobación o petición de ejecución
no duplica el registro ni vuelve a invocar el planificador o el ejecutor.
Las mutaciones críticas usan `BEGIN IMMEDIATE` y restricciones únicas.

## Operación por Telegram

```text
/ver_plan [id_tarea]
/responder_tarea <id_tarea> <respuesta>
/aprobar_tarea <id_tarea> <version> <huella_sha256>
```

La salida de `/ver_plan` contiene el prompt profesional, alcance, tecnologías,
fases, entregables, pruebas, riesgos, exclusiones, criterios de finalización,
versión y huella.

## Verificación

Las pruebas automatizadas cubren clasificación directa e indirecta, negativos,
texto citado, extracción de proyecto, ambigüedad, aclaraciones iterativas,
reparación del JSON, duplicados, idempotencia, versionado, aprobación de la
última versión, bloqueo previo a aprobación e integración con el flujo normal
de Telegram.
