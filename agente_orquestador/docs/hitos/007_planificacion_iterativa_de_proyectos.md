# Hito 7: PlanificaciÃ³n iterativa de proyectos desconocidos

**Fecha:** 25 de agosto de 2026
**Proyecto:** Agente Orquestador
**VersiÃ³n:** 0.1.0
**Estado:** Completado con limitaciones de calidad documentadas

## 1. Objetivo

El objetivo del Hito 7 es permitir que el Agente Orquestador reciba una peticiÃ³n incompleta para crear un proyecto desconocido, solicite aclaraciones, conserve las respuestas, genere una primera planificaciÃ³n tÃ©cnica y revise esa planificaciÃ³n mediante aclaraciones sucesivas.

El orquestador no debe escribir cÃ³digo durante este hito. Su responsabilidad termina cuando existe un plan versionado, comprensible y pendiente de aclaraciÃ³n o aprobaciÃ³n.

El recorrido general construido es:

```text
PeticiÃ³n inicial
â†’ clasificaciÃ³n como tarea
â†’ registro persistente
â†’ preguntas de aclaraciÃ³n
â†’ respuesta escrita o hablada
â†’ planificaciÃ³n tÃ©cnica
â†’ almacenamiento de la versiÃ³n
â†’ nuevas decisiones pendientes
â†’ nueva aclaraciÃ³n
â†’ nueva versiÃ³n del plan
```

## 2. Resultado funcional

El Hito 7 permite actualmente:

- Crear una tarea a partir de una peticiÃ³n escrita o hablada.
- Detectar el nombre del proyecto objetivo.
- Diferenciar proyectos conocidos y desconocidos.
- Formular preguntas especializadas para `agente_audioText`.
- Formular preguntas generales para cualquier proyecto desconocido.
- Guardar las tareas en SQLite.
- Guardar cada respuesta de aclaraciÃ³n sin borrar las anteriores.
- Generar planificaciones estructuradas mediante Ollama.
- Guardar varias versiones del plan.
- Marcar versiones anteriores como sustituidas.
- Mostrar tecnologÃ­as, interfaces, entradas y salidas.
- Mantener decisiones pendientes.
- Recibir aclaraciones mediante `/responder`.
- Recibir peticiones y aclaraciones mediante notas de voz de Telegram.
- Transcribir audio con Whisper.
- Mostrar modelo y tiempo de ejecuciÃ³n.
- Evitar la escritura de cÃ³digo antes de una autorizaciÃ³n posterior.

## 3. LÃ­mites del hito

Este hito no implementa todavÃ­a:

- AprobaciÃ³n de planes mediante `/aprobar`.
- EjecuciÃ³n automÃ¡tica de planes.
- CreaciÃ³n de carpetas o archivos de un proyecto.
- ModificaciÃ³n de repositorios externos.
- CoordinaciÃ³n de agentes especializados.
- ReanudaciÃ³n de una ejecuciÃ³n interrumpida.
- ValidaciÃ³n semÃ¡ntica completa de contradicciones entre requisitos confirmados y planes generados.

Estas capacidades deberÃ¡n abordarse en hitos posteriores.

## 4. SituaciÃ³n inicial

El Hito 6 dejÃ³ terminada la clasificaciÃ³n y el enrutamiento de peticiones.

Una peticiÃ³n como:

```text
Crea el proyecto agente_audioText
```

se clasificaba como:

```text
kind = task
project_name = agente_audioText
confidence = 0.90
```

El manejador provisional registraba la tarea, pero todavÃ­a no existÃ­an:

- Estados completos de planificaciÃ³n.
- Respuestas de aclaraciÃ³n persistentes.
- Planes estructurados.
- Versionado de planes.
- Comando `/responder`.
- Entrada mediante audio en el Agente Orquestador.

El Hito 6 terminÃ³ con 106 pruebas superadas.

## 5. Principio arquitectÃ³nico

Los canales externos no deben modificar la lÃ³gica del cerebro.

Telegram convierte cualquier entrada en un contrato comÃºn:

```text
Telegram texto â”€â”
                â”œâ†’ IncomingMessage â†’ Orchestrator
Telegram audio â”€â”˜
```

Una nota de voz no se trata como una herramienta. Es otro modo de entrada al mismo orquestador.

La transcripciÃ³n se realiza en el adaptador Telegram y el nÃºcleo recibe texto normalizado.

## 6. Arquitectura final del Hito 7

```mermaid
flowchart TD
    A[Telegram texto o audio] --> B[TelegramChannel]
    B --> C[IncomingMessage]
    C --> D[Orchestrator]
    D --> E[RequestClassifier]
    E --> F[TaskRepository]
    F --> G[ClarificationWorkflowService]
    G --> H[PlanningService]
    H --> I[OllamaProvider]
    H --> J[TaskPlanRepository]
    G --> K[TaskClarificationResponseRepository]
    J --> L[(SQLite)]
    K --> L
    F --> L
```

## 7. Estructura incorporada

```text
agente_orquestador/
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ audio/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â””â”€â”€ transcription_service.py
â”‚   â”œâ”€â”€ context/
â”‚   â”‚   â”œâ”€â”€ task_clarification_response_repository.py
â”‚   â”‚   â”œâ”€â”€ task_plan_repository.py
â”‚   â”‚   â””â”€â”€ task_repository.py
â”‚   â”œâ”€â”€ planning/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ clarification_workflow.py
â”‚   â”‚   â”œâ”€â”€ formatter.py
â”‚   â”‚   â”œâ”€â”€ models.py
â”‚   â”‚   â”œâ”€â”€ prompt_builder.py
â”‚   â”‚   â””â”€â”€ service.py
â”‚   â””â”€â”€ tasks/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ clarification_analyzer.py
â”‚       â”œâ”€â”€ clarification_response.py
â”‚       â”œâ”€â”€ models.py
â”‚       â””â”€â”€ state_machine.py
â””â”€â”€ tests/
    â”œâ”€â”€ test_clarification_workflow.py
    â”œâ”€â”€ test_planning_formatter.py
    â”œâ”€â”€ test_planning_models.py
    â”œâ”€â”€ test_planning_prompt_builder.py
    â”œâ”€â”€ test_planning_service.py
    â”œâ”€â”€ test_respond_command.py
    â”œâ”€â”€ test_task_clarification_analyzer.py
    â”œâ”€â”€ test_task_clarification_response.py
    â”œâ”€â”€ test_task_clarification_response_repository.py
    â”œâ”€â”€ test_task_models.py
    â”œâ”€â”€ test_task_plan_repository.py
    â”œâ”€â”€ test_task_repository.py
    â”œâ”€â”€ test_task_state_machine.py
    â”œâ”€â”€ test_telegram_voice_input.py
    â””â”€â”€ test_transcription_service.py
```

## 8. Modelo de tarea

`TaskRecord` representa una tarea persistente.

InformaciÃ³n principal:

- Identificador de tarea.
- Proyecto del Agente Orquestador al que pertenece.
- SesiÃ³n de Telegram.
- Mensaje que originÃ³ la tarea.
- TÃ­tulo.
- DescripciÃ³n.
- Proyecto objetivo.
- Estado.
- InformaciÃ³n pendiente.
- Plan provisional resumido.
- Fechas de creaciÃ³n, actualizaciÃ³n, autorizaciÃ³n y finalizaciÃ³n.

### 8.1 Estados de tarea

```text
pending_clarification
pending_planning
pending_approval
approved
cancelled
in_progress
completed
failed
```

### 8.2 Significado

| Estado | Significado |
|---|---|
| `pending_clarification` | Faltan decisiones del usuario |
| `pending_planning` | La informaciÃ³n puede convertirse en plan |
| `pending_approval` | Existe un plan sin decisiones bloqueantes |
| `approved` | El usuario autorizÃ³ el plan |
| `cancelled` | La tarea fue cancelada |
| `in_progress` | La ejecuciÃ³n ha comenzado |
| `completed` | La tarea terminÃ³ correctamente |
| `failed` | La tarea terminÃ³ con error |

### 8.3 MÃ¡quina de estados

Las transiciones permitidas se validan mediante `TaskStateMachine`.

```text
pending_planning
â”œâ†’ pending_clarification
â”œâ†’ pending_approval
â”œâ†’ cancelled
â””â†’ failed

pending_clarification
â”œâ†’ pending_planning
â”œâ†’ cancelled
â””â†’ failed

pending_approval
â”œâ†’ approved
â””â†’ cancelled

approved
â”œâ†’ in_progress
â””â†’ cancelled

in_progress
â”œâ†’ completed
â”œâ†’ failed
â””â†’ cancelled
```

Los estados terminales no permiten nuevas transiciones.

## 9. Persistencia SQLite

Durante el Hito 7 el esquema evolucionÃ³ hasta la versiÃ³n 5.

### 9.1 VersiÃ³n 3: tareas

Se aÃ±adiÃ³ la tabla `tasks`.

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    source_message_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_project_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending_planning',
    missing_information_json TEXT NOT NULL DEFAULT '[]',
    plan_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    authorized_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    UNIQUE (session_id, source_message_id)
);
```

La restricciÃ³n de unicidad evita registrar dos veces la misma actualizaciÃ³n de Telegram.

### 9.2 VersiÃ³n 4: respuestas de aclaraciÃ³n

Se aÃ±adiÃ³ `task_clarification_responses`.

```sql
CREATE TABLE IF NOT EXISTS task_clarification_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    response_message_id TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    UNIQUE (task_id, response_message_id)
);
```

Cada respuesta conserva:

- La tarea.
- El mensaje que contiene la respuesta.
- Las preguntas que estaban vigentes.
- La contestaciÃ³n del usuario.
- La fecha.

Guardar la instantÃ¡nea de las preguntas permite comprender posteriormente quÃ© estaba respondiendo el usuario.

### 9.3 VersiÃ³n 5: planes versionados

Se aÃ±adiÃ³ `task_plans`.

```sql
CREATE TABLE IF NOT EXISTS task_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL DEFAULT 'draft',
    objective TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '[]',
    technologies_json TEXT NOT NULL DEFAULT '[]',
    interfaces_json TEXT NOT NULL DEFAULT '[]',
    inputs_json TEXT NOT NULL DEFAULT '[]',
    outputs_json TEXT NOT NULL DEFAULT '[]',
    data_entities_json TEXT NOT NULL DEFAULT '[]',
    business_rules_json TEXT NOT NULL DEFAULT '[]',
    phases_json TEXT NOT NULL DEFAULT '[]',
    tests_json TEXT NOT NULL DEFAULT '[]',
    deployment_json TEXT NOT NULL DEFAULT '[]',
    pending_decisions_json TEXT NOT NULL DEFAULT '[]',
    excluded_items_json TEXT NOT NULL DEFAULT '[]',
    completion_criteria_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE,
    UNIQUE (task_id, version)
);
```

La migraciÃ³n se comprobÃ³ sobre la base real:

```text
Base: C:\Python_Proyectos\Agentes\agente_orquestador\data\context.db
VersiÃ³n: 5
Tabla task_plans: task_plans
Tareas conservadas: 2
```

La migraciÃ³n mantuvo intactas las tareas existentes.

## 10. Repositorio de tareas

`TaskRepository` permite:

- Crear tareas de forma idempotente.
- Recuperar por identificador.
- Recuperar por mensaje origen.
- Listar por proyecto y estado.
- Registrar informaciÃ³n pendiente.
- Volver a planificaciÃ³n.
- Asignar un plan resumido.
- Aprobar y cancelar.
- Validar que la sesiÃ³n pertenece al proyecto.

Cuando una aclaraciÃ³n ha sido guardada, `return_to_planning()` elimina las preguntas ya contestadas de la tarea:

```python
def return_to_planning(
    self,
    task_id: int,
) -> TaskRecord:
    task = self._get_required(task_id)

    self._state_machine.validate_transition(
        current_status=task.status,
        target_status=TaskStatus.PENDING_PLANNING,
    )

    self._database.connection.execute(
        """
        UPDATE tasks
        SET
            status = ?,
            missing_information_json = '[]',
            updated_at = strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                'now'
            )
        WHERE id = ?
        """,
        (
            TaskStatus.PENDING_PLANNING.value,
            task_id,
        ),
    )

    self._database.connection.commit()
    return self._get_required(task_id)
```

Las preguntas no se pierden porque permanecen en `task_clarification_responses`.

## 11. Contrato de respuesta de aclaraciÃ³n

`TaskClarificationResponse` contiene:

```text
id
task_id
response_message_id
questions
answer
created_at
```

El contrato normaliza espacios y rechaza:

- Identificadores no positivos.
- Mensajes vacÃ­os.
- Preguntas vacÃ­as.
- Respuestas vacÃ­as.

`TaskClarificationResponseRepository` garantiza idempotencia mediante:

```text
UNIQUE(task_id, response_message_id)
```

## 12. Preguntas especializadas y generales

`TaskClarificationAnalyzer` utiliza dos estrategias.

### 12.1 Perfil especializado de agente_audioText

Pregunta por:

1. Formatos de entrada.
2. Formato de salida.
3. Motor de voz.
4. Canal.
5. SelecciÃ³n de voz.

El analizador busca tÃ©rminos ya presentes para evitar repetir preguntas contestadas en la peticiÃ³n inicial.

### 12.2 Perfil general

Para cualquier proyecto desconocido pregunta:

1. Objetivo principal.
2. Tipo de aplicaciÃ³n.
3. Usuarios.
4. Funcionalidades.
5. InformaciÃ³n persistente.
6. Entorno de ejecuciÃ³n y acceso.
7. Restricciones o preferencias tecnolÃ³gicas.
8. Criterios de finalizaciÃ³n.

Este cuestionario no pretende resolver todo el proyecto. Su objetivo es reunir informaciÃ³n suficiente para una primera planificaciÃ³n.

Las preguntas posteriores deben surgir de la planificaciÃ³n generada.

## 13. Modelo de planificaciÃ³n

`TaskPlan` contiene:

```text
id
task_id
version
status
objective
scope
technologies
interfaces
inputs
outputs
data_entities
business_rules
phases
tests
deployment
pending_decisions
excluded_items
completion_criteria
created_at
updated_at
```

### 13.1 Estados del plan

```text
draft
pending_clarification
pending_approval
approved
superseded
```

### 13.2 Propiedades calculadas

Un plan requiere aclaraciones cuando contiene decisiones pendientes:

```python
@property
def requires_clarification(self) -> bool:
    return bool(self.pending_decisions)
```

Puede aprobarse cuando no existen decisiones pendientes y dispone de alcance, tecnologÃ­as, fases y criterios de finalizaciÃ³n:

```python
@property
def can_be_approved(self) -> bool:
    return (
        not self.pending_decisions
        and bool(self.scope)
        and bool(self.technologies)
        and bool(self.phases)
        and bool(self.completion_criteria)
    )
```

## 14. Versionado de planes

`TaskPlanRepository` calcula automÃ¡ticamente la siguiente versiÃ³n:

```sql
SELECT COALESCE(MAX(version), 0) + 1 AS next_version
FROM task_plans
WHERE task_id = ?;
```

Antes de insertar la nueva versiÃ³n marca como `superseded` los planes anteriores que todavÃ­a eran borrador, pendientes de aclaraciÃ³n o pendientes de aprobaciÃ³n.

```text
Plan versiÃ³n 1: superseded
Plan versiÃ³n 2: pending_clarification
```

Ninguna versiÃ³n se sobrescribe ni se elimina.

## 15. Constructor del prompt

`PlanningPromptBuilder` entrega al modelo:

- Identificador de tarea.
- TÃ­tulo.
- Proyecto objetivo.
- DescripciÃ³n inicial.
- Preguntas realizadas.
- Respuestas acumuladas.
- Instrucciones de planificaciÃ³n.
- Esquema JSON obligatorio.

Formato requerido:

```json
{
  "objective": "texto",
  "scope": ["texto"],
  "technologies": ["texto"],
  "interfaces": ["texto"],
  "inputs": ["texto"],
  "outputs": ["texto"],
  "data_entities": ["texto"],
  "business_rules": ["texto"],
  "phases": ["texto"],
  "tests": ["texto"],
  "deployment": ["texto"],
  "pending_decisions": ["texto"],
  "excluded_items": ["texto"],
  "completion_criteria": ["texto"]
}
```

El prompt ordena expresamente:

- Proponer tecnologÃ­as concretas.
- Identificar interfaces, entradas y salidas.
- Utilizar las aclaraciones como informaciÃ³n confirmada.
- No repetir preguntas contestadas.
- No escribir cÃ³digo.
- No afirmar que se han creado archivos.
- Devolver solamente JSON.

## 16. Servicio de planificaciÃ³n

`PlanningService` realiza este recorrido:

```text
obtener tarea
â†’ obtener aclaraciones
â†’ construir prompt
â†’ llamar LanguageProvider
â†’ extraer JSON
â†’ validar campos
â†’ crear TaskPlan
â†’ devolver GeneratedPlan
```

`GeneratedPlan` incluye:

```text
plan
model
elapsed_seconds
```

La validaciÃ³n rechaza:

- Respuesta vacÃ­a.
- Texto sin objeto JSON.
- JSON invÃ¡lido.
- Ausencia de objetivo.
- Campos que no sean listas.
- Listas con elementos que no sean textos.

Se admite JSON rodeado accidentalmente por un bloque Markdown, porque el servicio extrae el contenido entre la primera llave de apertura y la Ãºltima de cierre.

## 17. Flujo de aclaraciÃ³n

`ClarificationWorkflowService` coordina la operaciÃ³n completa:

```text
comprobar tarea
â†’ comprobar sesiÃ³n
â†’ comprobar estado pending_clarification
â†’ guardar respuesta
â†’ generar plan
â†’ volver temporalmente a pending_planning
â†’ evaluar decisiones pendientes
```

Si el plan contiene decisiones pendientes:

```text
tarea â†’ pending_clarification
```

Si no contiene decisiones pendientes:

```text
tarea â†’ pending_approval
```

El servicio valida que la tarea pertenece a la misma conversaciÃ³n. Un usuario no puede responder desde otra sesiÃ³n a una tarea ajena.

## 18. Formato de Telegram

`PlanningFormatter` genera una respuesta organizada:

```text
PLAN PROPUESTO â€” VERSIÃ“N N

Tarea
Proyecto
Estado

OBJETIVO
ALCANCE FUNCIONAL
TECNOLOGÃAS PROPUESTAS
INTERFACES
ENTRADAS
SALIDAS
ENTIDADES DE DATOS
REGLAS DE NEGOCIO
FASES DE CONSTRUCCIÃ“N
PRUEBAS PREVISTAS
DESPLIEGUE
ELEMENTOS EXCLUIDOS
CRITERIOS DE FINALIZACIÃ“N
DECISIONES PENDIENTES
```

Si existen decisiones pendientes muestra:

```text
/responder <id> <tus aclaraciones>
```

Si no existen, indica que la tarea estÃ¡ preparada para solicitar aprobaciÃ³n.

Siempre termina recordando:

```text
No se ha creado ni modificado cÃ³digo del proyecto.
```

## 19. Comando /responder

Formato escrito:

```text
/responder 3 La aplicaciÃ³n utilizarÃ¡ Angular, FastAPI y SQLite.
```

El orquestador valida:

- Presencia del identificador.
- Identificador entero positivo.
- Presencia de la respuesta.
- Existencia de la tarea.
- Pertenencia a la sesiÃ³n.
- Estado pendiente de aclaraciÃ³n.

Metadatos producidos:

```text
route = clarification_workflow
task_id
task_status
plan_id
plan_version
plan_status
model
elapsed_seconds
```

## 20. Entrada mediante audio

La conversiÃ³n de audio a texto reutiliza el diseÃ±o validado previamente en `agente_ia`.

Se creÃ³:

```text
app/audio/transcription_service.py
```

ConfiguraciÃ³n:

```dotenv
WHISPER_MODEL=small
```

Dependencia:

```text
faster-whisper
```

### 20.1 Servicio de transcripciÃ³n

ConfiguraciÃ³n utilizada:

```text
modelo: small
dispositivo: cpu
compute_type: int8
idioma: es
beam_size: 5
vad_filter: true
```

El modelo se carga de forma diferida en la primera nota de voz y se reutiliza en las siguientes.

### 20.2 PeticiÃ³n normal por audio

```text
Nota de voz
â†’ descargar OGG
â†’ transcribir
â†’ IncomingMessage(TEXT)
â†’ Orchestrator
```

Ejemplo hablado:

```text
Crea el proyecto puntuacion_padel
```

### 20.3 AclaraciÃ³n por audio

Primero se selecciona la tarea:

```text
/responder 3
```

Telegram guarda temporalmente:

```text
context.user_data["pending_audio_task_id"] = 3
```

La siguiente nota de voz se transforma internamente en:

```text
/responder 3 <texto transcrito>
```

Esto evita depender de que Whisper convierta correctamente la expresiÃ³n hablada â€œbarra responder tresâ€.

### 20.4 Archivos temporales

Los audios se descargan en:

```text
<directorio temporal>/agente_orquestador/telegram/
```

Se eliminan siempre mediante un bloque `finally`, tanto si la operaciÃ³n termina correctamente como si falla.

### 20.5 EjecuciÃ³n en segundo plano

La transcripciÃ³n y las llamadas largas a Ollama se ejecutan mediante:

```python
await asyncio.to_thread(...)
```

AsÃ­ se evita bloquear el bucle asÃ­ncrono de Telegram.

## 21. ConfiguraciÃ³n final

`.env.example` contiene:

```dotenv
AGENT_NAME=Agente Orquestador Pepe Millan
AGENT_VERSION=0.1.0
AGENT_ENVIRONMENT=development

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=

CONTEXT_DATABASE_PATH=data/context.db
PROJECT_NAME=Agente Orquestador
GIT_REPOSITORY=https://github.com/jmillan1955/Agentes.git

OLLAMA_BASE_URL=http://192.168.1.131:11434
OLLAMA_MODEL=qwen2.5-coder:3b
OLLAMA_TIMEOUT_SECONDS=300

WHISPER_MODEL=small
```

El archivo `.env` real continÃºa excluido de Git.

## 22. Dependencias

`requirements.txt`:

```text
pytest
python-dotenv
python-telegram-bot
httpx
faster-whisper
```

Durante el hito se detectÃ³ y corrigiÃ³ la errata:

```text
httpxS
```

por:

```text
httpx
```

## 23. EvoluciÃ³n de las pruebas

La evoluciÃ³n observada fue:

| Resultado | Capacidad incorporada |
|---:|---|
| 106 | Punto de partida del Hito 6 |
| 119 | Modelos de tarea |
| 123 | Esquema inicial de tareas |
| 132 | Repositorio de tareas |
| 133 | IntegraciÃ³n inicial con Orchestrator |
| 150 | MÃ¡quina de estados |
| 157 | Transiciones persistentes |
| 162 | Analizador de aclaraciones |
| 163 | Enrutamiento de tareas |
| 170 | Contrato de respuestas |
| 175 | Repositorio de aclaraciones |
| 189 | Modelos de planificaciÃ³n |
| 194 | Repositorio de planes |
| 198 | Constructor del prompt |
| 203 | Servicio de planificaciÃ³n |
| 206 | Flujo de aclaraciÃ³n |
| 209 | Formateador |
| 212 | Comando `/responder` |
| 213 | Preguntas para proyectos desconocidos |
| 217 | TranscripciÃ³n de audio |
| 220 | NormalizaciÃ³n de notas de voz |

Resultado final:

```text
220 passed
```

EjecuciÃ³n:

```powershell
cd C:\Python_Proyectos\Agentes\agente_orquestador
pytest -q
```

## 24. Incidencias resueltas

### 24.1 Pruebas no recopiladas

`tests/test_planning_models.py` contenÃ­a inicialmente solamente la funciÃ³n auxiliar `create_plan()`.

Pytest informÃ³:

```text
collected 0 items
```

Se aÃ±adieron funciones con prefijo `test_` y se incorporÃ³ el campo obligatorio `updated_at`.

### 24.2 ImportaciÃ³n circular

Se produjo el ciclo:

```text
app.context
â†’ task_plan_repository
â†’ app.planning
â†’ planning.service
â†’ app.context
```

Se solucionÃ³ mediante:

- Importaciones directas desde `app.planning.models`.
- Importaciones directas de repositorios concretos.
- ExclusiÃ³n de `PlanningService` del `app/planning/__init__.py`.

### 24.3 IndentaciÃ³n de Telegram

La incorporaciÃ³n parcial de nuevos manejadores provocaba riesgo de errores de indentaciÃ³n. Se sustituyÃ³ `telegram.py` completo para mantener una estructura coherente.

### 24.4 PlanificaciÃ³n lenta

El modelo local se ejecuta por CPU. Las planificaciones reales tardaron aproximadamente entre tres y tres minutos y medio.

El canal informa del progreso y aÃ±ade al resultado:

```text
Tiempo de ejecuciÃ³n
Modelo utilizado
```

### 24.5 CodificaciÃ³n visible en PowerShell

Algunas salidas de PowerShell mostraron caracteres como:

```text
Versi?n
aplicaciÃƒÂ³n
```

Los archivos deben mantenerse guardados en UTF-8. La visualizaciÃ³n incorrecta de una consola no debe corregirse introduciendo texto mal codificado en los fuentes.

## 25. Primera prueba funcional: puntuacion_padel

PeticiÃ³n:

```text
Crea el proyecto puntuacion_padel
```

El orquestador registrÃ³:

```text
Tarea #3
Proyecto: puntuacion_padel
Estado: pending_clarification
```

El usuario explicÃ³:

- Marcador de pÃ¡del.
- Equipos y participantes.
- Suma y correcciÃ³n de puntos.
- Control de juegos, sets y partido.
- Avisos de finalizaciÃ³n.
- AplicaciÃ³n web mÃ³vil.
- Historial persistente.
- Despliegue local y Ubuntu.
- TecnologÃ­a elegida por el orquestador.

### 25.1 Plan versiÃ³n 1

El modelo generÃ³ correctamente:

- Objetivo.
- Alcance.
- TecnologÃ­as.
- Interfaces.
- Entradas.
- Salidas.
- Entidades.
- Fases.
- Pruebas.
- Despliegue.
- Decisiones pendientes.

Tiempo:

```text
3,32 minutos
```

Modelo:

```text
qwen2.5-coder:3b
```

La primera versiÃ³n propuso alternativas demasiado abiertas, como React o Angular y MongoDB o Firebase. Esto motivÃ³ una segunda aclaraciÃ³n.

## 26. Segunda prueba funcional mediante audio

Se ejecutÃ³:

```text
/responder 3
```

DespuÃ©s se enviÃ³ una nota de voz con decisiones tÃ©cnicas y reglas del partido.

El flujo funcionÃ³ correctamente:

```text
selecciÃ³n de tarea
â†’ descarga del audio
â†’ transcripciÃ³n
â†’ almacenamiento de la aclaraciÃ³n
â†’ Ollama
â†’ Plan versiÃ³n 2
```

Tiempo:

```text
3,12 minutos
```

Modelo:

```text
qwen2.5-coder:3b
```

La entrada mediante audio se considerÃ³ muy satisfactoria.

## 27. LimitaciÃ³n de calidad detectada

Aunque la infraestructura funcionÃ³ correctamente, el Plan versiÃ³n 2 contradijo informaciÃ³n confirmada.

El usuario habÃ­a indicado:

```text
Angular
FastAPI
SQLite
API REST
Ubuntu
Caddy
sin MongoDB
sin Firebase
sin WebSocket
mejor de tres sets
tie-break a siete
ventaja o punto de oro configurable
```

El modelo devolviÃ³, entre otras cosas:

```text
Flask en lugar de FastAPI
Kubernetes en lugar de Ubuntu con Caddy
â€œTybaltâ€ en lugar de tie-break
preguntas repetidas sobre decisiones ya contestadas
```

ConclusiÃ³n:

```text
Infraestructura: correcta
Persistencia: correcta
Versionado: correcto
Audio: correcto
Fidelidad semÃ¡ntica del plan: mejorable
```

El Plan versiÃ³n 2 no debe aprobarse.

## 28. DecisiÃ³n de diseÃ±o para el prÃ³ximo hito

Antes de permitir `/aprobar`, el orquestador deberÃ¡ disponer de requisitos confirmados estructurados.

Propuesta:

```text
Respuesta del usuario
â†’ extracciÃ³n de requisitos confirmados
â†’ almacenamiento estructurado
â†’ generaciÃ³n del plan
â†’ validaciÃ³n contra requisitos
â†’ correcciÃ³n si hay contradicciones
â†’ presentaciÃ³n al usuario
```

CategorÃ­as mÃ­nimas:

- Objetivos confirmados.
- TecnologÃ­as confirmadas.
- TecnologÃ­as prohibidas.
- Interfaces confirmadas.
- Entorno de despliegue.
- Reglas de negocio confirmadas.
- Decisiones pendientes.
- Criterios de finalizaciÃ³n.

Un plan no podrÃ¡ pasar a `pending_approval` si contradice estos requisitos.

## 29. Seguridad

Se mantienen estas garantÃ­as:

- Solo se acepta el usuario de Telegram configurado.
- Las tareas se validan contra la sesiÃ³n actual.
- `.env` no se publica.
- SQLite local no se publica.
- Las respuestas de aclaraciÃ³n son idempotentes.
- Los planes anteriores no se eliminan.
- No se escribe cÃ³digo durante la planificaciÃ³n.
- No se ejecutan comandos de sistema.
- No se modifica Git desde Telegram.

## 30. Comprobaciones antes del commit

Desde la raÃ­z del repositorio:

```powershell
cd C:\Python_Proyectos\Agentes

git status --short -- .\agente_orquestador
```

Ejecutar pruebas:

```powershell
cd .\agente_orquestador
pytest -q
```

Resultado esperado:

```text
220 passed
```

Volver a la raÃ­z y aÃ±adir solamente el proyecto:

```powershell
cd C:\Python_Proyectos\Agentes

git add -- .\agente_orquestador
```

Comprobar errores de espacios:

```powershell
git --no-pager diff --cached --check
```

Revisar resumen:

```powershell
git status --short -- .\agente_orquestador

git --no-pager diff --cached --stat
```

Commit propuesto:

```powershell
git commit -m "Completar planificaciÃ³n iterativa de proyectos"
```

PublicaciÃ³n:

```powershell
git push origin master
```

ComprobaciÃ³n:

```powershell
git log -1 --oneline

git status --short -- .\agente_orquestador
```

## 31. Criterios de aceptaciÃ³n

El Hito 7 se considera completado porque:

- Una peticiÃ³n desconocida genera una tarea.
- La tarea se guarda en SQLite.
- Se solicitan aclaraciones generales.
- Las respuestas se conservan.
- Se genera un plan estructurado.
- El plan incluye tecnologÃ­a e interfaces.
- Los planes se versionan.
- Las versiones anteriores se conservan.
- Se pueden realizar aclaraciones sucesivas.
- La entrada puede ser escrita o hablada.
- El audio se transcribe correctamente.
- Telegram permanece receptivo durante operaciones largas.
- No se escribe cÃ³digo.
- Existen 220 pruebas automÃ¡ticas superadas.
- La limitaciÃ³n de fidelidad semÃ¡ntica ha quedado identificada y documentada.

## 32. Punto exacto de continuaciÃ³n

El siguiente hito debe comenzar sin ejecutar proyectos todavÃ­a.

Primer objetivo:

```text
Construir un almacÃ©n estructurado de requisitos confirmados.
```

DespuÃ©s:

```text
Validar el plan generado contra esos requisitos.
```

Solo cuando el plan sea consistente se aÃ±adirÃ¡:

```text
/aprobar <tarea_id>
```

El futuro recorrido serÃ¡:

```text
Plan vÃ¡lido
â†’ pending_approval
â†’ /aprobar
â†’ approved
â†’ preparaciÃ³n de ejecuciÃ³n
```

La ejecuciÃ³n real de cÃ³digo deberÃ¡ permanecer separada y requerir una autorizaciÃ³n explÃ­cita.

## 33. Resultado final

El Agente Orquestador ha evolucionado desde un clasificador de mensajes hasta un sistema capaz de mantener una conversaciÃ³n de descubrimiento sobre proyectos desconocidos.

Ya puede recibir una idea inicial, formular preguntas, escuchar respuestas escritas o habladas, generar una arquitectura propuesta, conservar mÃºltiples versiones y detenerse antes de ejecutar cambios.

El Hito 7 queda cerrado con la planificaciÃ³n iterativa operativa y con una limitaciÃ³n conocida: antes de aprobar planes serÃ¡ necesario garantizar que el modelo respeta de forma estricta los requisitos confirmados por el usuario.