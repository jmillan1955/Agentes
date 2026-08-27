# Hito 8: Aprobación y autorización segura de planes

**Fecha:** 26 de agosto de 2026
**Proyecto:** Agente Orquestador
**Versión:** 0.1.0
**Estado:** Completado y validado localmente

## 1. Objetivo

El objetivo del Hito 8 es incorporar una frontera explícita y auditable entre la planificación de una tarea y su futura ejecución.

Un plan puede generarse y revisarse tantas veces como sea necesario, pero ninguna tarea debe quedar autorizada para ejecutarse hasta que un usuario aprobador confirme una versión exacta mediante Telegram.

El hito también permite revocar una autorización antes de que comience la ejecución. La revocación cancela la tarea, conserva el plan aprobado y mantiene el registro original de autorización como evidencia histórica.

El recorrido construido es:

```text
Tarea pendiente de aclaración
→ respuestas vinculantes
→ nueva versión del plan
→ plan sin decisiones bloqueantes
→ tarea pendiente de aprobación
→ consulta mediante /ver_plan
→ aprobación mediante /aprobar
→ autorización persistente y auditable
→ tarea preparada para una futura ejecución controlada
```

El recorrido alternativo de revocación es:

```text
Tarea aprobada
→ /cancelar
→ tarea cancelada
→ plan aprobado conservado
→ autorización histórica conservada
→ ejecución bloqueada
```

## 2. Resultado funcional

El Hito 8 permite:

- Separar usuarios autorizados para usar Telegram de usuarios autorizados para aprobar planes.
- Configurar uno o varios aprobadores mediante variables de entorno.
- Exigir que todos los aprobadores pertenezcan también a la lista de usuarios permitidos.
- Consultar la última versión de un plan mediante `/ver_plan <tarea_id>`.
- Aprobar una versión exacta mediante `/aprobar <tarea_id>`.
- Registrar tarea, plan, versión, usuario, mensaje, canal y fecha de autorización.
- Aprobar de forma atómica la tarea y el plan.
- Repetir `/aprobar` sin generar autorizaciones duplicadas.
- Revisar un plan que ya estaba pendiente de aprobación mediante `/responder`.
- Tratar las aclaraciones confirmadas como decisiones vinculantes.
- Evitar que el modelo vuelva a presentar como pendiente una decisión ya respondida.
- Cancelar una tarea aprobada mediante `/cancelar <tarea_id>`.
- Repetir `/cancelar` de forma idempotente.
- Conservar el plan aprobado y la autorización original después de cancelar.
- Impedir que una tarea cancelada pueda iniciar una ejecución futura.
- Mantener la garantía de que este hito no crea ni modifica código del proyecto objetivo.

## 3. Límites del hito

Este hito no implementa todavía:

- Ejecución automática del plan aprobado.
- Creación de carpetas o archivos en el proyecto objetivo.
- Modificación de repositorios externos.
- Uso de agentes especializados de implementación, pruebas o despliegue.
- Reanudación de una ejecución interrumpida.
- Registro de pasos ejecutados.
- Aislamiento de una ejecución en un espacio de trabajo temporal.
- Confirmaciones adicionales para operaciones destructivas.

Estas capacidades corresponden al Hito 9 y a hitos posteriores.

## 4. Situación inicial

El Hito 7 permitía crear tareas, solicitar aclaraciones, generar planes estructurados y conservar versiones sucesivas.

Los planes podían terminar en:

- `pending_clarification`, cuando existían decisiones pendientes.
- `pending_approval`, cuando el plan estaba completo.

Sin embargo, todavía no existían:

- Usuarios aprobadores diferenciados.
- Un comando de aprobación.
- Una autorización persistente.
- Un vínculo auditable entre una autorización y una versión concreta.
- Un comando para consultar el plan vigente.
- Un mecanismo de revocación.

## 5. Principios de seguridad

### 5.1. Autorización explícita

La existencia de un plan completo no equivale a permiso de ejecución. La autorización requiere un comando explícito de un usuario aprobador.

### 5.2. Aprobación de una versión exacta

La autorización guarda `plan_id` y `plan_version`. Si posteriormente se genera otra versión, la autorización anterior no debe trasladarse silenciosamente al nuevo plan.

### 5.3. Mínimo privilegio

Los cuatro miembros configurados pueden utilizar el bot, pero solamente José puede aprobar o cancelar tareas aprobadas.

### 5.4. Persistencia atómica

La tarea, el plan y la autorización deben cambiar dentro de una única transacción. Si falla cualquiera de las operaciones, se revierte todo el conjunto.

### 5.5. Idempotencia

Repetir `/aprobar` o `/cancelar` no debe crear duplicados ni producir estados incoherentes.

### 5.6. Auditoría inmutable

Cancelar una tarea no borra la autorización. La autorización demuestra quién aprobó qué versión, mediante qué mensaje y en qué momento.

### 5.7. Sin ejecución implícita

Una aprobación solamente cambia el estado a `approved`. El Hito 8 no interpreta la aprobación como una orden para escribir código.

## 6. Configuración de usuarios aprobadores

Se añadió la variable:

```dotenv
TELEGRAM_APPROVER_USER_IDS=8288969559
```

La configuración diferencia:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=8288969559,177448510,8683027220,1446339382
TELEGRAM_APPROVER_USER_IDS=8288969559
```

Reglas aplicadas por `Settings.load()`:

- La lista de aprobadores es obligatoria.
- Los valores deben ser enteros separados por comas.
- Se eliminan identificadores duplicados conservando el orden.
- Debe existir al menos un aprobador.
- Todo aprobador debe estar incluido en `TELEGRAM_ALLOWED_USER_IDS`.

El contrato incorporado a `Settings` es:

```python
telegram_allowed_user_ids: tuple[int, ...]
telegram_approver_user_ids: tuple[int, ...]
```

La configuración real `.env` no se incluye en Git. `.env.example` documenta las variables sin publicar el token del bot.

## 7. Estados de tarea y plan

### 7.1. Estados relevantes de la tarea

```text
pending_planning
pending_clarification
pending_approval
approved
in_progress
completed
failed
cancelled
```

### 7.2. Estados relevantes del plan

```text
draft
pending_clarification
pending_approval
approved
superseded
```

### 7.3. Transiciones añadidas o utilizadas

```text
pending_clarification → pending_planning
pending_planning → pending_approval
pending_approval → pending_planning
pending_approval → approved
approved → cancelled
```

La transición `pending_approval → pending_planning` permite corregir un plan completo antes de aprobarlo mediante una nueva llamada a `/responder`.

La transición `approved → cancelled` permite revocar una autorización antes de iniciar la ejecución.

Los estados terminales continúan sin transiciones posteriores:

```text
completed
failed
cancelled
```

## 8. Modelo de autorización

El archivo `app/approvals/models.py` define `TaskApproval` como un contrato inmutable:

```python
@dataclass(frozen=True, slots=True)
class TaskApproval:
    id: int
    task_id: int
    plan_id: int
    plan_version: int
    authorized_user_id: str
    authorization_message_id: str
    channel: str
    created_at: str
```

Cada autorización identifica de forma inequívoca:

- La tarea autorizada.
- El plan autorizado.
- La versión exacta.
- El usuario aprobador.
- El mensaje de Telegram que originó la autorización.
- El canal de entrada.
- La fecha UTC de creación.

## 9. Esquema SQLite versión 6

La versión del esquema pasó a:

```python
SCHEMA_VERSION = 6
```

Se añadió la tabla `task_approvals` con las restricciones necesarias para impedir duplicados:

```sql
CREATE TABLE IF NOT EXISTS task_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL UNIQUE,
    plan_id INTEGER NOT NULL UNIQUE,
    plan_version INTEGER NOT NULL,
    authorized_user_id TEXT NOT NULL,
    authorization_message_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    FOREIGN KEY (task_id)
        REFERENCES tasks(id),
    FOREIGN KEY (plan_id)
        REFERENCES task_plans(id),
    UNIQUE (channel, authorization_message_id)
);
```

También se añadió un índice para consultas de auditoría por usuario y fecha.

Las restricciones garantizan:

- Una única autorización por tarea.
- Una única autorización por plan.
- Un mensaje de un canal no puede autorizar dos veces.

Antes de migrar la base de datos local se conservó una copia de seguridad. Los archivos de base de datos y sus copias no se incluyen en Git.

## 10. Repositorio de autorizaciones

El archivo `app/context/task_approval_repository.py` implementa la persistencia.

La operación de aprobación:

1. Inicia `BEGIN IMMEDIATE`.
2. Recupera la tarea.
3. Recupera el último plan de la tarea.
4. Comprueba que la tarea está pendiente de aprobación.
5. Comprueba que el plan está pendiente de aprobación.
6. Comprueba que no existen decisiones pendientes.
7. Actualiza el plan exacto a `approved`.
8. Actualiza la tarea a `approved` y fija `authorized_at`.
9. Inserta `task_approvals`.
10. Confirma la transacción.

Ante cualquier error se ejecuta `ROLLBACK`.

Si la tarea ya estaba aprobada, el repositorio recupera la autorización original. De esta forma, la repetición del comando no genera una segunda fila ni sustituye la fecha inicial.

## 11. Servicio de aprobación

`app/approvals/service.py` separa las reglas de negocio del canal Telegram y de SQLite.

Errores del dominio:

```python
class ApprovalError(Exception):
    pass

class ApprovalPermissionError(ApprovalError):
    pass

class ApprovalValidationError(ApprovalError):
    pass
```

Resultado de aprobación:

```python
@dataclass(frozen=True, slots=True)
class ApprovalResult:
    approval: TaskApproval
    task: TaskRecord
    plan: TaskPlan
    already_approved: bool
```

Resultado de cancelación:

```python
@dataclass(frozen=True, slots=True)
class CancellationResult:
    approval: TaskApproval
    task: TaskRecord
    plan: TaskPlan
    cancelled_user_id: str
    already_cancelled: bool
```

El servicio verifica los permisos antes de aprobar o cancelar. Los identificadores se convierten a texto para compararlos de forma consistente con `IncomingMessage.user_id`.

## 12. Cancelación segura

El método `ApprovalService.cancel()` aplica estas reglas:

1. El identificador de tarea debe ser positivo.
2. El usuario debe pertenecer a la lista de aprobadores.
3. Debe existir una autorización previa para la tarea.
4. Deben poder recuperarse la tarea y el plan autorizado.
5. Solamente una tarea `approved` puede cancelarse por primera vez.
6. Si ya está `cancelled`, se devuelve un resultado idempotente.
7. La tarea pasa a `cancelled`.
8. El plan permanece `approved`.
9. La fila de `task_approvals` permanece intacta.

La cancelación no significa que el plan fuera incorrecto. Significa que se revoca el permiso para ejecutarlo.

## 13. Comandos de Telegram

### 13.1. Consultar el plan

```text
/ver_plan 3
```

Muestra la última versión almacenada, incluyendo el estado aprobado cuando corresponda.

### 13.2. Aprobar

```text
/aprobar 3
```

Solo funciona si:

- El usuario es aprobador.
- La tarea está pendiente de aprobación.
- La última versión no contiene decisiones pendientes.
- El plan contiene alcance, tecnologías, fases y criterios de finalización.

### 13.3. Cancelar

```text
/cancelar 4
```

Solo funciona para un aprobador y para una tarea que tenga una autorización registrada.

### 13.4. Revisar antes de aprobar

```text
/responder 3 <correcciones>
```

También se admite cuando la tarea está `pending_approval`. La tarea vuelve temporalmente a planificación, se genera una nueva versión y la versión anterior queda sustituida.

## 14. Integración en el orquestador

`app/orchestrator.py` recibe `TaskPlanRepository`, `ApprovalService` y `ApprovalFormatter` mediante inyección de dependencias.

Los comandos devuelven metadatos estructurados.

Metadatos principales de aprobación:

```text
route=approval_service
task_id
task_status
plan_id
plan_version
approval_id
authorized_user_id
already_approved
```

Metadatos principales de cancelación:

```text
route=cancellation_service
task_id
task_status
plan_id
plan_version
plan_status
approval_id
cancelled_user_id
already_cancelled
```

El orquestador captura errores del dominio y los convierte en respuestas comprensibles sin exponer trazas internas al usuario de Telegram.

## 15. Integración en Telegram

`app/channels/telegram.py` registra:

```python
CommandHandler("ver_plan", self.handle_view_plan)
CommandHandler("aprobar", self.handle_approve)
CommandHandler("cancelar", self.handle_cancel)
```

Los manejadores no contienen reglas de aprobación. Convierten la actualización en `ContentType.COMMAND` y delegan en `_process_update()`.

Esta separación mantiene el canal como adaptador y evita duplicar lógica de negocio.

## 16. Formato de respuestas

`ApprovalFormatter` genera mensajes diferenciados para:

- Plan aprobado por primera vez.
- Plan ya aprobado anteriormente.
- Tarea aprobada cancelada por primera vez.
- Tarea ya cancelada anteriormente.

La respuesta de cancelación indica explícitamente:

- Tarea y proyecto.
- Versión del plan aprobado que se conserva.
- Usuario que solicita la cancelación.
- Conservación histórica de la autorización.
- Bloqueo de la ejecución.
- Ausencia de creación o modificación de código.

## 17. Mejora de la planificación vinculante

Durante la validación real, el modelo volvió a presentar como pendiente una decisión que el usuario ya había resuelto.

Se aplicaron dos defensas complementarias.

### 17.1. Instrucción al modelo

`PlanningPromptBuilder` presenta las respuestas bajo el encabezado:

```text
DECISIONES CONFIRMADAS Y VINCULANTES
```

El prompt ordena:

- No volver a preguntar decisiones respondidas.
- No ofrecer alternativas incompatibles.
- Incorporar literalmente las decisiones definitivas.

### 17.2. Filtro determinista

`PlanningService` normaliza texto, elimina acentos y compara tokens significativos entre preguntas respondidas y nuevas decisiones pendientes.

El filtro elimina una decisión pendiente cuando repite semánticamente una cuestión ya contestada, pero conserva decisiones realmente nuevas.

El modelo continúa ayudando a construir el plan, mientras que el código protege una regla crítica del flujo.

## 18. Revisión desde `pending_approval`

La primera implementación de `/responder` solo aceptaba tareas `pending_clarification`.

La revisión humana detectó errores como:

- `FADS API` en lugar de `FastAPI`.
- Alternativas tecnológicas no deseadas.
- Reglas deportivas incompletas.
- Fases que describían funciones en lugar de construcción técnica.

Se permitió revisar una tarea `pending_approval`:

```text
pending_approval
→ pending_planning
→ generación de nueva versión
→ pending_clarification o pending_approval
```

También se adaptó `TaskClarificationResponseRepository` para guardar respuestas tanto durante aclaración como durante revisión.

## 19. Incidencias y correcciones

### 19.1. Importación circular

Problema:

```text
task_approval_repository
→ app.approvals
→ service
→ task_approval_repository
```

Solución:

- `app/approvals/__init__.py` exporta únicamente el modelo básico.
- Los servicios se importan desde su módulo concreto.
- El repositorio importa `TaskApproval` desde `app.approvals.models`.

### 19.2. Variables de entorno contaminando pruebas

Algunas pruebas de Ollama fallaban antes de validar Ollama porque el aprobador heredado no pertenecía a la lista de usuarios permitidos preparada por el test.

Se corrigieron los datos comunes de prueba para que cada prueba configure un entorno coherente.

### 19.3. Problemas de codificación

Existían textos con mojibake como `nÃºmero` o `aprobaciÃ³n`. Las pruebas comparaban en algunos casos el texto dañado.

Los mensajes nuevos se escribieron con texto estable y se corrigieron expectativas concretas. El repositorio debe mantenerse en UTF-8.

### 19.4. Decisiones respondidas que reaparecían

El modelo generó varias versiones manteniendo como pendiente el punto de oro, el número de sets y el desempate, aunque ya estaban confirmados.

Se reforzó el prompt y se añadió el filtro determinista descrito anteriormente.

### 19.5. Tiempo de respuesta de Ollama

Una generación superó el límite de 300 segundos. Para las pruebas reales se amplió localmente el tiempo de espera a 600 segundos.

La modificación de `.env` es local y no debe publicarse.

### 19.6. Revisión bloqueada

Una tarea en `pending_approval` no admitía `/responder`. Se añadió la transición inversa controlada y se ampliaron las validaciones del repositorio de aclaraciones.

### 19.7. Doble numeración de fases

El modelo devolvió fases como `1. Definir arquitectura`, y el formateador añadió otro prefijo, produciendo `1. 1. Definir arquitectura`.

`PlanningFormatter` elimina el prefijo previo antes de numerar la sección.

### 19.8. Indentación de `cancel()`

Durante la incorporación manual, `cancel()` quedó anidado dentro de `approve()`, provocando `IndentationError` y ausencia del método público.

Se corrigió la definición al nivel de clase y se comprobó con `py_compile` antes de continuar.

### 19.9. Archivo de Telegram sin guardar

La primera compilación de `telegram.py` mostró un error de indentación aunque el bloque visible ya era correcto. El archivo todavía no se había guardado en VS Code.

Después de `Ctrl+S`, `py_compile` confirmó la sintaxis correcta.

### 19.10. Espacio final

`git diff --check` detectó un espacio final en `app/orchestrator.py`. Se eliminó y la segunda comprobación terminó limpia.

## 20. Evolución real del plan `puntuacion_padel`

La tarea real utilizada para validar el flujo fue la `#3`.

Las versiones iniciales contenían decisiones pendientes y errores de calidad. Las aclaraciones sucesivas fijaron:

- Angular para el frontend.
- FastAPI para el backend.
- SQLite como base de datos.
- Ubuntu con `systemd` detrás de Caddy.
- Partido al mejor de tres sets.
- Victoria para el primer equipo que gana dos sets.
- Set a seis juegos con dos de diferencia.
- Desempate a siete puntos en 6-6, con diferencia de dos.
- Punto de oro en 40-40.
- Entidades Partido, Equipo, Jugador, Set, Juego y EventoPuntuacion.
- Pruebas de punto de oro, juegos, sets, desempate, partido completo y corrección del último punto.

La versión 7 corrigió las fases para describir una secuencia técnica de construcción.

## 21. Evidencia de aprobación real

La tarea `#3` fue aprobada mediante Telegram.

Estado persistido:

```text
task_status: approved
authorized_at: 2026-08-26T12:26:41.248Z
plan_id: 7
plan_version: 7
plan_status: approved
approval_id: 1
authorized_user_id: 8288969559
authorization_message_id: telegram:8288969559:165
channel: telegram
created_at: 2026-08-26T12:26:41.248Z
```

La consulta `/ver_plan 3` mostró la versión 7 como aprobada y confirmó:

```text
El plan ya esta aprobado.
No se ha iniciado ninguna ejecucion.
```

## 22. Prueba funcional de cancelación

Para no alterar la tarea real `#3`, se creó una tarea temporal:

```text
TAREA_TEMPORAL=4
PLAN_TEMPORAL=8
ESTADO=pending_approval
```

Resultado de la prueba:

```text
APROBACION: approved approved 2
CANCELACION: cancelled approved False
REPETICION: cancelled approved True
```

Interpretación:

- La tarea temporal quedó cancelada.
- El plan temporal permaneció aprobado.
- La autorización se conservó.
- La repetición fue idempotente.

Después de la prueba se verificó expresamente la tarea real:

```text
TAREA_3: approved 2026-08-26T12:26:41.248Z
PLAN_3: 7 7 approved
APROBACION_3: 1 8288969559
```

## 23. Pruebas automatizadas

Se añadieron pruebas para:

- Modelo de autorización.
- Validación de campos.
- Repositorio y transacción atómica.
- Aprobación correcta.
- Aprobador no autorizado.
- Plan incompleto o con decisiones pendientes.
- Aprobación repetida.
- Formato de aprobación.
- Cancelación correcta.
- Cancelación por usuario no autorizado.
- Cancelación sin autorización previa.
- Cancelación repetida.
- Formato de cancelación.
- Comandos del orquestador.
- Metadatos de aprobación y cancelación.
- Manejadores de Telegram.
- Consulta del plan.
- Revisión desde `pending_approval`.
- Eliminación de decisiones ya respondidas.
- Conservación de decisiones nuevas.
- Numeración de fases.

Pruebas específicas del conjunto de aprobación, orquestador y Telegram:

```text
57 passed in 0.80s
```

Suite completa final:

```text
285 passed in 3.60s
```

Comprobación de formato:

```text
git diff --check -- .
```

Resultado final: sin errores.

## 24. Archivos principales incorporados

Nuevos:

```text
app/approvals/__init__.py
app/approvals/models.py
app/approvals/service.py
app/approvals/formatter.py
app/context/task_approval_repository.py
tests/test_approval_models.py
tests/test_task_approval_repository.py
tests/test_approval_service.py
tests/test_approval_formatter.py
```

Modificados principalmente:

```text
.env.example
app/channels/telegram.py
app/context/__init__.py
app/context/schema.py
app/context/task_clarification_response_repository.py
app/orchestrator.py
app/planning/clarification_workflow.py
app/planning/formatter.py
app/planning/prompt_builder.py
app/planning/service.py
app/tasks/state_machine.py
config.py
main.py
```

También se actualizaron las pruebas correspondientes.

## 25. Comandos de verificación

```powershell
python -m py_compile `
    .\app\approvals\service.py `
    .\app\approvals\formatter.py `
    .\app\orchestrator.py `
    .\app\channels\telegram.py

pytest -q

git diff --check -- .
```

## 26. Despliegue previsto en Ubuntu

Después de publicar el commit:

```bash
cd /home/jose-millan/Agentes
git pull --ff-only

cd agente_orquestador
source ../.venv/bin/activate
pytest -q
```

La configuración privada de Ubuntu debe contener:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=8288969559,177448510,8683027220,1446339382
TELEGRAM_APPROVER_USER_IDS=8288969559
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_GENERAL_MODEL=llama3.2:3b
OLLAMA_CODING_MODEL=qwen2.5-coder:3b
OLLAMA_TIMEOUT_SECONDS=600
```

El token real no debe aparecer en documentación, consola compartida ni Git.

## 27. Estado final del Hito 8

El sistema dispone de una frontera segura entre planificación y ejecución:

- Existe un plan versionado.
- El plan puede revisarse antes de aprobar.
- Solo José puede aprobar.
- La aprobación identifica una versión exacta.
- La autorización queda persistida y es auditable.
- La aprobación repetida es segura.
- Una tarea aprobada puede cancelarse antes de ejecutar.
- La cancelación conserva el historial.
- La tarea real `#3` permanece aprobada.
- No se ha ejecutado ni modificado código de `puntuacion_padel`.

## 28. Continuación exacta: Hito 9

El siguiente hito debe implementar la ejecución controlada de planes aprobados.

El punto de partida es:

```text
Tarea #3
Proyecto puntuacion_padel
Estado approved
Plan #7, versión 7, estado approved
Autorización #1
Aprobador 8288969559
Sin ejecución iniciada
```

Antes de escribir código del proyecto objetivo, el Hito 9 deberá definir:

1. Un modelo persistente de ejecución.
2. Estados de ejecución y transiciones permitidas.
3. Un identificador de ejecución asociado a tarea, plan y autorización.
4. Un directorio de trabajo permitido y validado.
5. Límites para impedir escritura fuera del proyecto objetivo.
6. Registro de cada paso ejecutado.
7. Captura de salida, errores y tiempos.
8. Política de reintentos y reanudación.
9. Comandos de inicio, consulta y cancelación de ejecución.
10. Confirmación adicional para operaciones destructivas.
11. Pruebas con un proyecto temporal antes de ejecutar `puntuacion_padel`.
12. Despliegue controlado y recuperación ante fallos.

La primera acción del Hito 9 no debe ser ejecutar el plan real. Debe ser diseñar y probar el subsistema de ejecución con tareas y directorios temporales.