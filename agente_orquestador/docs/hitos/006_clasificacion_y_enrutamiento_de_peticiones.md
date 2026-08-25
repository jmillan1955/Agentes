# Hito 6: ClasificaciÃ³n y enrutamiento de peticiones

**Fecha:** 25 de agosto de 2026

**Proyecto:** Agente Orquestador

**VersiÃ³n:** 0.1.0

**Estado:** Completado

## 1. SituaciÃ³n inicial

Al comenzar este hito, el Agente Orquestador ya disponÃ­a de:

- Canal de entrada y salida mediante Telegram.
- Contratos comunes `IncomingMessage` y `OutgoingMessage`.
- Persistencia de proyectos, sesiones, mensajes, documentos y commits en SQLite.
- SincronizaciÃ³n de documentos Markdown y del historial de Git.
- Consulta resumida del contexto mediante `/contexto`.
- BÃºsqueda de informaciÃ³n mediante `/buscar`.
- RecuperaciÃ³n de contexto relevante.
- GeneraciÃ³n de respuestas utilizando Ollama.
- Registro del modelo y del tiempo de ejecuciÃ³n.
- 84 pruebas automatizadas superadas al terminar el hito 5.

Todos los mensajes normales se trataban como preguntas y se enviaban a Ollama. El sistema todavÃ­a no diferenciaba entre una consulta y una solicitud para realizar cambios.

Esto suponÃ­a un problema para el objetivo final del proyecto. Una peticiÃ³n como:

```text
Crea el proyecto agente_audioText
```

no debe tratarse como una pregunta. Debe reconocerse como una tarea, planificarse y esperar autorizaciÃ³n antes de modificar archivos.

## 2. Objetivo

Incorporar una primera capa de comprensiÃ³n y enrutamiento capaz de:

- Clasificar los mensajes recibidos.
- Diferenciar preguntas, consultas de proyecto, tareas y comandos.
- Detectar el proyecto mencionado.
- Guardar la decisiÃ³n en SQLite.
- Permitir probar la clasificaciÃ³n desde Telegram.
- Enviar las preguntas al proveedor de lenguaje.
- Desviar las tareas a un manejador seguro.
- Evitar que una tarea provoque cambios automÃ¡ticamente.

## 3. Alcance

En este hito se implementa:

- ClasificaciÃ³n local basada en reglas.
- Contrato normalizado de decisiÃ³n.
- DetecciÃ³n inicial de proyectos.
- Comando `/clasificar`.
- Persistencia de metadatos de enrutamiento.
- Manejador provisional de tareas.
- Enrutamiento efectivo entre comandos, tareas y preguntas.

## 4. Funciones aplazadas

Este hito no permite todavÃ­a:

- Crear proyectos.
- Crear o modificar archivos.
- Ejecutar comandos del sistema.
- Generar planes de trabajo.
- Mantener una conversaciÃ³n de aclaraciÃ³n.
- Autorizar o cancelar una tarea.
- Ejecutar pruebas de un proyecto generado.
- Crear commits o publicar automÃ¡ticamente.

Estas capacidades se incorporarÃ¡n progresivamente a partir del hito 7.

## 5. Arquitectura resultante

El flujo de entrada queda dividido segÃºn la decisiÃ³n de enrutamiento:

```text
Telegram
â†’ IncomingMessage
â†’ Orchestrator
â†’ RequestClassifier
   â”œâ”€â”€ command       â†’ procesador de comandos
   â”œâ”€â”€ task          â†’ ProvisionalTaskHandler
   â”œâ”€â”€ general_query â†’ ResponseGenerationService â†’ Ollama
   â””â”€â”€ project_query â†’ contexto â†’ ResponseGenerationService â†’ Ollama
â†’ OutgoingMessage
â†’ SQLite
â†’ Telegram
```

La clasificaciÃ³n basada en reglas no llama a Ollama y se ejecuta prÃ¡cticamente de forma inmediata.

## 6. Tipos de peticiÃ³n: RequestKind

Se creÃ³ la enumeraciÃ³n `RequestKind` para representar los tipos de entrada que el orquestador puede reconocer.

```python
class RequestKind(str, Enum):
    GENERAL_QUERY = "general_query"
    PROJECT_QUERY = "project_query"
    TASK = "task"
    CLARIFICATION = "clarification"
    COMMAND = "command"
```

### 6.1. general_query

Pregunta general que no depende de un proyecto concreto.

Ejemplo:

```text
Â¿QuÃ© es SQLite?
```

Recorrido:

```text
general_query
â†’ ResponseGenerationService
â†’ Ollama
```

### 6.2. project_query

Consulta relacionada con un proyecto, su documentaciÃ³n, contexto, cÃ³digo o historial.

Ejemplo:

```text
Â¿DÃ³nde guarda el Agente Orquestador su contexto?
```

Recorrido:

```text
project_query
â†’ recuperar contexto relevante
â†’ ResponseGenerationService
â†’ Ollama
```

### 6.3. task

PeticiÃ³n que implica crear, modificar, eliminar, instalar, publicar o realizar alguna acciÃ³n.

Ejemplo:

```text
Crea el proyecto agente_audioText
```

Recorrido actual:

```text
task
â†’ ProvisionalTaskHandler
â†’ pending_planning
```

La tarea se reconoce, pero no se ejecuta.

### 6.4. clarification

PeticiÃ³n para la que falta informaciÃ³n imprescindible.

Este tipo queda definido en el contrato, aunque la conversaciÃ³n de aclaraciÃ³n se desarrollarÃ¡ durante el hito 7.

### 6.5. command

Orden interna del agente, identificada porque comienza por `/`.

Ejemplos:

```text
/contexto
/buscar SQLite
/clasificar AÃ±ade un canal de correo
```

## 7. Contrato de decisiÃ³n: RoutingDecision

`RoutingDecision` representa el resultado normalizado del clasificador.

Contiene:

| Campo | DescripciÃ³n |
|---|---|
| `kind` | Tipo de peticiÃ³n reconocido. |
| `summary` | Texto normalizado que resume la peticiÃ³n. |
| `confidence` | Confianza entre 0.0 y 1.0. |
| `project_name` | Proyecto detectado, si existe. |
| `missing_information` | InformaciÃ³n necesaria que todavÃ­a falta. |

La propiedad:

```python
requires_clarification
```

devuelve `True` cuando la decisiÃ³n es de tipo `clarification` o existe informaciÃ³n pendiente.

El contrato valida que:

- El resumen no estÃ© vacÃ­o.
- La confianza estÃ© entre 0 y 1.
- Los textos se guarden sin espacios exteriores.
- Se eliminen entradas vacÃ­as de `missing_information`.

## 8. CÃ³digo completo de app/routing/models.py

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RequestKind(str, Enum):
    GENERAL_QUERY = "general_query"
    PROJECT_QUERY = "project_query"
    TASK = "task"
    CLARIFICATION = "clarification"
    COMMAND = "command"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    kind: RequestKind
    summary: str
    confidence: float
    project_name: str | None = None
    missing_information: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        clean_summary = self.summary.strip()

        if not clean_summary:
            raise ValueError(
                "summary no puede estar vacÃ­o"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence debe estar "
                "entre 0 y 1"
            )

        clean_project_name = (
            self.project_name.strip()
            if self.project_name is not None
            else None
        )

        clean_missing_information = tuple(
            value.strip()
            for value in self.missing_information
            if value.strip()
        )

        object.__setattr__(
            self,
            "summary",
            clean_summary,
        )
        object.__setattr__(
            self,
            "project_name",
            clean_project_name or None,
        )
        object.__setattr__(
            self,
            "missing_information",
            clean_missing_information,
        )

    @property
    def requires_clarification(self) -> bool:
        return (
            self.kind == RequestKind.CLARIFICATION
            or bool(self.missing_information)
        )
```

## 9. Clasificador inicial

Se creÃ³ `RequestClassifier` como clasificador determinista basado en reglas.

Se decidiÃ³ no realizar una llamada independiente a Ollama para clasificar porque el servidor trabaja actualmente con CPU y una segunda inferencia duplicarÃ­a aproximadamente el tiempo de respuesta.

Ventajas de la clasificaciÃ³n local:

- Respuesta inmediata.
- Comportamiento predecible.
- Pruebas rÃ¡pidas.
- Funcionamiento sin conexiÃ³n con Ollama.
- Ausencia de coste adicional de inferencia.

Limitaciones:

- Las reglas no entienden todavÃ­a todos los matices del lenguaje natural.
- Una frase ambigua puede clasificarse de forma incorrecta.
- La detecciÃ³n de informaciÃ³n ausente es todavÃ­a bÃ¡sica.
- Los verbos no registrados pueden requerir nuevas reglas.

## 10. Reglas utilizadas

Los comandos se reconocen por `/` al comienzo.

Las tareas se reconocen inicialmente por verbos como:

```text
aÃ±ade
actualiza
borra
cambia
construye
crea
corrige
desarrolla
elimina
genera
implementa
instala
modifica
prepara
publica
```

El texto se normaliza mediante Unicode NFKD para eliminar diferencias entre mayÃºsculas, minÃºsculas y acentos durante la comparaciÃ³n.

Esto permite reconocer de la misma forma:

```text
Crea
crea
CrÃ©a
```

## 11. DetecciÃ³n de proyectos

El clasificador reconoce referencias explÃ­citas al Agente Orquestador mediante tÃ©rminos como:

```text
Agente Orquestador
contexto SQLite
context.db
hito
repositorio
```

TambiÃ©n extrae el nombre situado despuÃ©s de `proyecto`, incluyendo las variantes `proyecto llamado` y `proyecto denominado`.

Ejemplo:

```text
Crea el proyecto agente_audioText
```

Resultado:

```text
Tipo: task
Proyecto: agente_audioText
Confianza: 90%
```

Durante la prueba funcional se descubriÃ³ que considerar la palabra genÃ©rica `proyecto` como sinÃ³nimo de `Agente Orquestador` producÃ­a una identificaciÃ³n incorrecta. La detecciÃ³n se corrigiÃ³ para extraer primero el nombre especÃ­fico del nuevo proyecto.

## 12. CÃ³digo completo de app/routing/request_classifier.py

```python
from __future__ import annotations

import re
import unicodedata

from app.routing.models import (
    RequestKind,
    RoutingDecision,
)


class RequestClassifier:
    _TASK_VERBS = {
        "anade",
        "actualiza",
        "borra",
        "cambia",
        "construye",
        "crea",
        "corrige",
        "desarrolla",
        "elimina",
        "genera",
        "implementa",
        "instala",
        "modifica",
        "prepara",
        "publica",
    }

    _ORCHESTRATOR_TERMS = {
        "agente orquestador",
        "contexto sqlite",
        "context.db",
        "hito",
        "repositorio",
    }

    _GENERIC_PROJECT_WORDS = {
        "el",
        "la",
        "su",
        "un",
        "una",
        "nuevo",
        "nueva",
    }

    def classify(
        self,
        text: str,
    ) -> RoutingDecision:
        clean_text = text.strip()

        if not clean_text:
            raise ValueError(
                "text no puede estar vacÃ­o"
            )

        normalized_text = self._normalize(
            clean_text
        )

        if normalized_text.startswith("/"):
            return RoutingDecision(
                kind=RequestKind.COMMAND,
                summary=clean_text,
                confidence=1.0,
            )

        first_word = self._first_word(
            normalized_text
        )

        project_name = self._detect_project(
            original_text=clean_text,
            normalized_text=normalized_text,
        )

        if first_word in self._TASK_VERBS:
            return RoutingDecision(
                kind=RequestKind.TASK,
                summary=clean_text,
                confidence=0.90,
                project_name=project_name,
            )

        if project_name is not None:
            return RoutingDecision(
                kind=RequestKind.PROJECT_QUERY,
                summary=clean_text,
                confidence=0.85,
                project_name=project_name,
            )

        return RoutingDecision(
            kind=RequestKind.GENERAL_QUERY,
            summary=clean_text,
            confidence=0.70,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize(
            "NFKD",
            text,
        )

        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        return without_accents.lower().strip()

    @staticmethod
    def _first_word(text: str) -> str:
        match = re.search(
            r"[a-z0-9_]+",
            text,
        )

        if match is None:
            return ""

        return match.group(0)

    def _detect_project(
        self,
        original_text: str,
        normalized_text: str,
    ) -> str | None:
        if (
            "agente orquestador"
            in normalized_text
        ):
            return "Agente Orquestador"

        project_match = re.search(
            (
                r"\bproyecto"
                r"(?:\s+(?:llamado|denominado))?"
                r"\s+"
                r"([A-Za-zÃÃ‰ÃÃ“ÃšÃœÃ‘"
                r"Ã¡Ã©Ã­Ã³ÃºÃ¼Ã±0-9_-]+)"
            ),
            original_text,
            flags=re.IGNORECASE,
        )

        if project_match is not None:
            candidate = (
                project_match.group(1).strip()
            )

            normalized_candidate = (
                self._normalize(candidate)
            )

            if (
                normalized_candidate
                not in self._GENERIC_PROJECT_WORDS
            ):
                return candidate

        if any(
            term in normalized_text
            for term in self._ORCHESTRATOR_TERMS
        ):
            return "Agente Orquestador"

        if "proyecto" in normalized_text:
            return "Agente Orquestador"

        return None
```

## 13. Comando /clasificar

Se incorporÃ³ el comando:

```text
/clasificar <peticiÃ³n>
```

Permite probar el clasificador sin ejecutar acciones y sin consultar Ollama.

Ejemplo:

```text
/clasificar AÃ±ade un canal de correo
```

Respuesta:

```text
CLASIFICACIÃ“N DE LA PETICIÃ“N

PeticiÃ³n: AÃ±ade un canal de correo
Tipo: task
Confianza: 90%
Necesita aclaraciÃ³n: No
```

Consulta de proyecto:

```text
/clasificar Â¿DÃ³nde guarda el proyecto su contexto?
```

Respuesta:

```text
CLASIFICACIÃ“N DE LA PETICIÃ“N

PeticiÃ³n: Â¿DÃ³nde guarda el proyecto su contexto?
Tipo: project_query
Confianza: 85%
Necesita aclaraciÃ³n: No
Proyecto: Agente Orquestador
```

Si no se proporciona argumento, se responde:

```text
Debes indicar una peticiÃ³n.

Ejemplo:
/clasificar AÃ±ade un canal de correo
```

## 14. Diferencia entre comando y argumento clasificado

El mensaje completo:

```text
/clasificar AÃ±ade un canal de correo
```

es un comando. Por ello, el metadato principal almacenado es:

```text
routing_kind: command
routing_confidence: 1.0
```

El argumento interno se clasifica como:

```text
task
confianza: 0.90
```

No existe contradicciÃ³n: son dos niveles distintos.

## 15. Persistencia en SQLite

La decisiÃ³n se incorpora a los metadatos del `OutgoingMessage` relacionado con la entrada.

Ejemplo de una tarea normal:

```json
{
  "processor": "orchestrator",
  "session_id": 1,
  "routing_kind": "task",
  "routing_confidence": 0.9,
  "routing_summary": "Crea el proyecto agente_audioText",
  "routing_project": "agente_audioText",
  "routing_requires_clarification": false,
  "route": "task_handler",
  "task_status": "pending_planning",
  "task_project": "agente_audioText"
}
```

Los mensajes `incoming` conservan los metadatos originales de Telegram. La decisiÃ³n se guarda en la respuesta relacionada mediante `correlation_id`.

## 16. Manejador provisional de tareas

Se creÃ³ `ProvisionalTaskHandler` para impedir que las tareas se envÃ­en como preguntas normales al proveedor de lenguaje.

Responsabilidades:

- Aceptar Ãºnicamente decisiones `task`.
- Mostrar el resumen de la tarea.
- Mostrar el proyecto detectado.
- Mostrar la confianza.
- Asignar el estado `pending_planning`.
- Confirmar que no se ha realizado ningÃºn cambio.

## 17. CÃ³digo completo de app/routing/task_handler.py

```python
from __future__ import annotations

from dataclasses import dataclass

from app.routing.models import (
    RequestKind,
    RoutingDecision,
)


@dataclass(frozen=True, slots=True)
class TaskHandlingResult:
    text: str
    status: str
    project_name: str | None


class ProvisionalTaskHandler:
    def handle(
        self,
        decision: RoutingDecision,
    ) -> TaskHandlingResult:
        if decision.kind != RequestKind.TASK:
            raise ValueError(
                "ProvisionalTaskHandler solamente "
                "acepta peticiones de tipo task"
            )

        project_name = (
            decision.project_name
            or "Sin determinar"
        )

        lines = [
            "PETICIÃ“N IDENTIFICADA COMO TAREA",
            "",
            f"Resumen: {decision.summary}",
            f"Proyecto: {project_name}",
            (
                "Confianza: "
                f"{decision.confidence:.0%}"
            ),
            "Estado: pendiente de planificaciÃ³n",
            "",
            (
                "No se ha ejecutado ningÃºn cambio. "
                "La tarea deberÃ¡ ser planificada "
                "y autorizada antes de comenzar."
            ),
        ]

        return TaskHandlingResult(
            text="\n".join(lines),
            status="pending_planning",
            project_name=decision.project_name,
        )
```

## 18. CÃ³digo completo de app/routing/__init__.py

```python
from app.routing.models import (
    RequestKind,
    RoutingDecision,
)
from app.routing.request_classifier import (
    RequestClassifier,
)
from app.routing.task_handler import (
    ProvisionalTaskHandler,
    TaskHandlingResult,
)


__all__ = [
    "ProvisionalTaskHandler",
    "RequestClassifier",
    "RequestKind",
    "RoutingDecision",
    "TaskHandlingResult",
]
```

## 19. IntegraciÃ³n con Orchestrator

El constructor recibe:

```python
request_classifier: RequestClassifier | None = None
task_handler: ProvisionalTaskHandler | None = None
```

Si no se proporcionan, crea las implementaciones predeterminadas.

Para entradas de texto o comandos, el orquestador crea una `RoutingDecision` y aÃ±ade sus datos a los metadatos.

La selecciÃ³n principal es:

```python
if message.content_type == ContentType.COMMAND:
    response_text = self._process_command(...)

elif message.content_type == ContentType.TEXT:
    if decision.kind == RequestKind.TASK:
        task_result = self._task_handler.handle(
            decision
        )
    else:
        answer = (
            self._response_generation_service
            .generate(...)
        )
```

Las tareas incorporan:

```json
{
  "route": "task_handler",
  "task_status": "pending_planning"
}
```

Las respuestas del modelo incorporan:

```json
{
  "route": "language_provider",
  "model": "qwen2.5-coder:3b",
  "elapsed_seconds": 49.0
}
```

## 20. IntegraciÃ³n con main.py

Se crean e inyectan expresamente:

```python
request_classifier=RequestClassifier()
task_handler=ProvisionalTaskHandler()
```

Esto mantiene visible la composiciÃ³n de dependencias y permitirÃ¡ sustituirlas mÃ¡s adelante.

## 21. IntegraciÃ³n con Telegram

Se registrÃ³:

```python
CommandHandler(
    "clasificar",
    self.handle_classify,
)
```

El canal registra ahora todos los mensajes recibidos:

```text
Mensaje recibido: tipo=command, id=telegram:...
```

El aviso previo se generalizÃ³ a:

```text
PeticiÃ³n recibida. Procesando...
```

Esta expresiÃ³n sirve tanto para preguntas como para tareas.

## 22. Decisiones de seguridad

Una clasificaciÃ³n `task` no concede permiso para ejecutar la tarea.

En este hito se aplican las siguientes reglas:

- No crear archivos.
- No modificar archivos.
- No borrar archivos.
- No ejecutar comandos.
- No realizar commits.
- No publicar cambios.
- No utilizar automÃ¡ticamente credenciales.
- No interpretar una peticiÃ³n como autorizaciÃ³n implÃ­cita.

El estado `pending_planning` indica que la tarea debe pasar por planificaciÃ³n y confirmaciÃ³n.

## 23. Proceso de construcciÃ³n

El hito se desarrollÃ³ en pequeÃ±as fases:

1. Crear `RequestKind` y `RoutingDecision`.
2. Validar contratos y normalizaciÃ³n.
3. Crear `RequestClassifier`.
4. Probar comandos, preguntas y tareas.
5. Integrar la decisiÃ³n como metadatos.
6. AÃ±adir `/clasificar` a Telegram.
7. Verificar la persistencia en SQLite.
8. Crear `ProvisionalTaskHandler`.
9. Evitar llamadas a Ollama para tareas.
10. Detectar nombres de proyectos nuevos.
11. Realizar la prueba funcional completa.

EvoluciÃ³n de las pruebas:

```text
84 â†’ 91 â†’ 98 â†’ 99 â†’ 101 â†’ 104 â†’ 105 â†’ 106
```

## 24. Pruebas automatizadas

Se crearon:

```text
tests/test_routing_models.py
tests/test_request_classifier.py
tests/test_task_handler.py
```

Se modificÃ³:

```text
tests/test_orchestrator.py
```

Las pruebas verifican:

- CreaciÃ³n de decisiones.
- ValidaciÃ³n del resumen.
- ValidaciÃ³n de confianza.
- NormalizaciÃ³n de textos.
- ClasificaciÃ³n de comandos.
- ClasificaciÃ³n de preguntas generales.
- ClasificaciÃ³n de consultas de proyecto.
- ClasificaciÃ³n de tareas.
- Reconocimiento de acentos.
- ExtracciÃ³n de nombres de proyectos.
- Manejador provisional.
- Rechazo de tipos incompatibles.
- Metadatos de enrutamiento.
- Comando `/clasificar`.
- ValidaciÃ³n cuando falta el argumento.
- Ausencia de llamadas a Ollama para tareas.
- ConservaciÃ³n del control de errores del proveedor.

Resultado final:

```text
106 passed in 2.27s
```

## 25. Incidencias Ãºtiles

### 25.1. CodificaciÃ³n de PowerShell

En una prueba enviada mediante un bloque de PowerShell, algunos caracteres aparecieron como `?`:

```text
AÃ±ade â†’ A?ade
```

El clasificador recibiÃ³ un texto ya alterado y no pudo reconocer el verbo.

La prueba con una secuencia Unicode confirmÃ³ que el cÃ³digo funcionaba correctamente:

```python
text = "\u0041\u00f1ade un canal de correo"
```

Telegram transmite Unicode correctamente, por lo que no fue necesario modificar el clasificador para aceptar texto corrupto.

### 25.2. Prueba antigua del proveedor

La prueba de error del proveedor utilizaba:

```text
Genera una respuesta
```

DespuÃ©s de incorporar el enrutamiento, `Genera` se reconocÃ­a correctamente como tarea y ya no llegaba al proveedor.

La prueba se corrigiÃ³ utilizando una pregunta general:

```text
Â¿CuÃ¡l es la capital de Portugal?
```

Este resultado confirmÃ³ que las tareas estaban siendo desviadas correctamente.

### 25.3. Bot incorrecto en Telegram

Durante una prueba no aparecÃ­a actividad porque Telegram habÃ­a abierto el bot anterior de `agente_ia`.

El bot correcto es:

```text
@AgenteOrquestadorPepeMillanBot
```

### 25.4. IdentificaciÃ³n inicial incorrecta

La primera prueba de:

```text
Crea el proyecto agente_audioText
```

mostrÃ³:

```text
Proyecto: Agente Orquestador
```

La causa era que la palabra `proyecto` se asociaba genÃ©ricamente con el Orquestador. Se aÃ±adiÃ³ la extracciÃ³n del nombre situado despuÃ©s de `proyecto`, obteniendo finalmente:

```text
Proyecto: agente_audioText
```

## 26. Pruebas funcionales

### 26.1. ClasificaciÃ³n de tarea

Entrada:

```text
/clasificar AÃ±ade un canal de correo
```

Salida:

```text
CLASIFICACIÃ“N DE LA PETICIÃ“N

PeticiÃ³n: AÃ±ade un canal de correo
Tipo: task
Confianza: 90%
Necesita aclaraciÃ³n: No
```

### 26.2. ClasificaciÃ³n de consulta

Entrada:

```text
/clasificar Â¿DÃ³nde guarda el proyecto su contexto?
```

Salida:

```text
CLASIFICACIÃ“N DE LA PETICIÃ“N

PeticiÃ³n: Â¿DÃ³nde guarda el proyecto su contexto?
Tipo: project_query
Confianza: 85%
Necesita aclaraciÃ³n: No
Proyecto: Agente Orquestador
```

### 26.3. Enrutamiento real de una tarea

Entrada normal, sin comando:

```text
Crea el proyecto agente_audioText
```

Salida:

```text
PETICIÃ“N IDENTIFICADA COMO TAREA

Resumen: Crea el proyecto agente_audioText
Proyecto: agente_audioText
Confianza: 90%
Estado: pendiente de planificaciÃ³n

No se ha ejecutado ningÃºn cambio. La tarea deberÃ¡ ser planificada y autorizada antes de comenzar.
```

La respuesta fue inmediata y no mostrÃ³ modelo ni tiempo de inferencia, confirmando que Ollama no intervino.

## 27. Archivos creados

```text
app/routing/__init__.py
app/routing/models.py
app/routing/request_classifier.py
app/routing/task_handler.py
tests/test_request_classifier.py
tests/test_routing_models.py
tests/test_task_handler.py
docs/hitos/006_clasificacion_y_enrutamiento_de_peticiones.md
```

## 28. Archivos modificados

```text
app/channels/telegram.py
app/orchestrator.py
main.py
tests/test_orchestrator.py
```

## 29. Comandos de comprobaciÃ³n

CompilaciÃ³n:

```powershell
python -m py_compile `
  .\app\routing\models.py `
  .\app\routing\request_classifier.py `
  .\app\routing\task_handler.py `
  .\app\orchestrator.py `
  .\app\channels\telegram.py `
  .\main.py
```

Pruebas:

```powershell
pytest -q
```

EjecuciÃ³n:

```powershell
python main.py
```

## 30. Procedimiento Git

Desde la raÃ­z del repositorio:

```powershell
git status --short -- .\agente_orquestador
```

PreparaciÃ³n:

```powershell
git add -- `
  .\agente_orquestador\app `
  .\agente_orquestador\main.py `
  .\agente_orquestador\tests `
  .\agente_orquestador\docs\hitos\006_clasificacion_y_enrutamiento_de_peticiones.md
```

ComprobaciÃ³n:

```powershell
git --no-pager diff --cached --check
git status --short -- .\agente_orquestador
```

Commit previsto:

```powershell
git commit -m "Completar clasificaciÃ³n y enrutamiento de peticiones"
```

PublicaciÃ³n:

```powershell
git push origin master
```

VerificaciÃ³n:

```powershell
git status --short -- .\agente_orquestador
git log -2 --oneline
```

## 31. Resultado final

El Agente Orquestador ya puede:

- Clasificar una entrada.
- Distinguir una pregunta de una tarea.
- Reconocer comandos.
- Detectar el proyecto mencionado.
- Mostrar la clasificaciÃ³n mediante Telegram.
- Guardar la decisiÃ³n en SQLite.
- Enviar preguntas al proveedor de lenguaje.
- Desviar tareas al manejador provisional.
- Evitar que una tarea ejecute cambios sin autorizaciÃ³n.

El hito 6 queda completado.

## 32. Punto exacto de continuaciÃ³n

Estado al terminar:

```text
106 pruebas superadas
/clasificar operativo
ClasificaciÃ³n persistida en SQLite
Tareas enrutadas a ProvisionalTaskHandler
Proyecto agente_audioText detectado correctamente
Estado de tareas: pending_planning
```

## 33. PrÃ³ximo hito

El hito 7 incorporarÃ¡ planificaciÃ³n, aclaraciones y autorizaciÃ³n.

La peticiÃ³n inicial de referencia serÃ¡:

```text
Crea el proyecto agente_audioText
```

El objetivo serÃ¡ transformarla en una tarea persistente que pueda:

- Detectar la informaciÃ³n que falta.
- Formular preguntas al usuario.
- Guardar las respuestas.
- Crear un plan de trabajo.
- Mostrar el plan mediante Telegram.
- Esperar autorizaciÃ³n explÃ­cita.
- Permitir cancelar la tarea.

TodavÃ­a no se permitirÃ¡ crear archivos ni ejecutar comandos hasta que exista una autorizaciÃ³n controlada.