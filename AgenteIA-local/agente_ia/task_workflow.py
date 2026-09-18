"""Triaje y ciclo de vida auditable para solicitudes de trabajo.

El modulo mantiene separadas cuatro responsabilidades deliberadamente:

* clasificar una entrada sin efectos secundarios;
* construir y validar un plan estructurado;
* registrar la aprobacion explicita de una version concreta;
* impedir cualquier ejecucion que no tenga esa aprobacion.

No contiene dependencias de Telegram ni de un proveedor de modelos. Esa
separacion permite probar las garantias criticas sin red y reutilizar el flujo
desde otros canales en el futuro.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Iterator, Protocol


MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807
PLAN_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _validate_approval_input(
    task_id: int,
    *,
    conversation_id: int,
    version: int,
    plan_hash: str,
    approved_by: int,
    source_key: str,
) -> None:
    integer_fields = (task_id, conversation_id, version, approved_by)
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_SQLITE_INTEGER
        for value in integer_fields
    ):
        raise ApprovalError("los datos de aprobacion no son validos")
    if not isinstance(plan_hash, str) or PLAN_HASH_PATTERN.fullmatch(plan_hash) is None:
        raise ApprovalError("la huella del plan no es valida")
    if not isinstance(source_key, str) or not source_key.strip():
        raise ApprovalError("la clave idempotente no es valida")


class IntentKind(str, Enum):
    COMMAND = "command"
    QUERY = "query"
    TASK = "task"
    CLARIFICATION = "clarification"


@dataclass(frozen=True)
class RoutingDecision:
    kind: IntentKind
    confidence: float
    project: str | None = None
    context: str | None = None
    reason: str = ""
    missing_information: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanPhase:
    name: str
    objective: str
    deliverables: tuple[str, ...]


@dataclass(frozen=True)
class StructuredPlan:
    objective: str
    professional_prompt: str
    scope: tuple[str, ...]
    technologies: tuple[str, ...]
    phases: tuple[PlanPhase, ...]
    tests: tuple[str, ...]
    risks: tuple[str, ...]
    exclusions: tuple[str, ...]
    completion_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TaskRecord:
    id: int
    conversation_id: int
    source_key: str
    request_text: str
    confidence: float
    project: str | None
    context: str | None
    status: str
    missing_information: tuple[str, ...]


@dataclass(frozen=True)
class PlanRecord:
    id: int
    task_id: int
    version: int
    status: str
    plan: StructuredPlan
    plan_hash: str
    raw_response: str


@dataclass(frozen=True)
class ApprovalRecord:
    id: int
    task_id: int
    plan_id: int
    plan_version: int
    plan_hash: str
    approved_by: int


@dataclass(frozen=True)
class ExecutionRecord:
    id: int
    task_id: int
    plan_id: int
    plan_version: int
    plan_hash: str
    requested_by: int
    state: str


@dataclass(frozen=True)
class WorkflowOutcome:
    decision: RoutingDecision
    task: TaskRecord | None = None
    plan: PlanRecord | None = None
    questions: tuple[str, ...] = ()
    created: bool = False


class TaskWorkflowError(RuntimeError):
    """Error de dominio visible y seguro para el canal de entrada."""


class PlanGenerationError(TaskWorkflowError):
    pass


class ApprovalError(TaskWorkflowError):
    pass


class ExecutionBlockedError(TaskWorkflowError):
    pass


class PlanningProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


class CallablePlanningProvider:
    """Adapta una funcion async sencilla al protocolo de planificacion."""

    def __init__(self, callback: Callable[[str], Awaitable[str]]) -> None:
        self._callback = callback

    async def complete(self, prompt: str) -> str:
        return await self._callback(prompt)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def _without_quoted_content(value: str) -> str:
    result = value
    result = re.sub(r"```.*?```", " ", result, flags=re.DOTALL)
    result = re.sub(r"`[^`\n]*`", " ", result)
    result = re.sub(r'"(?:\\.|[^"\\])*"', " ", result)
    result = re.sub(r"“[^”]*”|«[^»]*»", " ", result, flags=re.DOTALL)
    return result


class TaskIntentClassifier:
    """Clasificador determinista conservador para no inventar tareas."""

    _ACTION_ROOTS = (
        "constru",
        "escrib",
        "planific",
        "crea",
        "implement",
        "modific",
        "corrig",
        "desarroll",
        "anad",
        "agreg",
        "actualiz",
        "refactoriz",
        "prepar",
        "configur",
        "integra",
        "automatiz",
        "gener",
        "repar",
        "solucion",
    )
    _DIRECT_RE = re.compile(
        r"^(?:por favor\s+)?(?:quiero que\s+)?"
        r"(?:construye|construyan|escribe|planifica|crea|implementa|modifica|"
        r"corrige|desarrolla|anade|agrega|actualiza|refactoriza|prepara|"
        r"configura|integra|automatiza|genera|repara|soluciona|haz)\b"
    )
    _IMPERATIVE_RE = re.compile(
        r"\b(?:construye|escribe|planifica|crea|implementa|modifica|corrige|"
        r"desarrolla|anade|agrega|actualiza|refactoriza|prepara|configura|"
        r"integra|automatiza|genera|repara|soluciona|haz)\b"
    )
    _INDIRECT_RE = re.compile(
        r"\b(?:quiero|necesito|me gustaria)\s+que\s+(?:me\s+)?"
        r"(?:construyas|escribas|planifiques|crees|implementes|modifiques|"
        r"corrijas|desarrolles|anadas|agregues|actualices|refactorices|"
        r"prepares|configures|integres|automatices|generes|repares|soluciones)\b|"
        r"\b(?:quiero|necesito|me gustaria)\s+"
        r"(?:construir|escribir|planificar|crear|implementar|modificar|"
        r"corregir|desarrollar|anadir|agregar|actualizar|refactorizar|"
        r"preparar|configurar|integrar|automatizar|generar|reparar|solucionar)\b|"
        r"\b(?:puedes|podrias)\s+(?:por favor\s+)?"
        r"(?:construir|escribir|planificar|crear|implementar|modificar|"
        r"corregir|desarrollar|anadir|agregar|actualizar|refactorizar|"
        r"preparar|configurar|integrar|automatizar|generar|reparar|solucionar|hacer)\b|"
        r"\b(?:encargate de|vamos a|hay que)\s+"
        r"(?:construir|escribir|planificar|crear|implementar|modificar|"
        r"corregir|desarrollar|anadir|agregar|actualizar|refactorizar|"
        r"preparar|configurar|integrar|automatizar|generar|reparar|solucionar|hacer)\b"
    )
    _KNOWLEDGE_RE = re.compile(
        r"^(?:me\s+)?(?:explica|explicame|describe|define|cuentame)|"
        r"^(?:quiero|necesito)\s+(?:saber|entender|conocer)\b|"
        r"^(?:que|como|cuando|donde|por que|para que|cual|cuales)\b"
    )
    _VAGUE_RE = re.compile(
        r"\b(?:esto|este|esta|estos|estas|eso|aquello|lo anterior|lo de antes|el tema)\b"
    )
    _DESCRIPTIVE_RE = re.compile(
        r"\b(?:el comando|la funcion|el metodo|la clase|este codigo|ese codigo)\s+"
        r"(?:construye|escribe|planifica|crea|implementa|modifica|corrige|"
        r"genera|repara|soluciona)\b"
    )
    _PATH_RE = re.compile(r"\b[A-Za-z]:\\[^\r\n]+")
    _KNOWN_PROJECTS = {
        "agenteia-local": "AgenteIA-local",
        "agente ia local": "AgenteIA-local",
        "home assistant": "Home Assistant",
        "agente orquestador": "agente_orquestador",
    }

    def classify(self, text: str, *, has_pending_task: bool = False) -> RoutingDecision:
        stripped = text.strip()
        if stripped.startswith("/"):
            return RoutingDecision(IntentKind.COMMAND, 1.0, reason="comando explicito")

        unquoted = _without_quoted_content(stripped)
        normalized = re.sub(r"\s+", " ", _normalize(unquoted)).strip(" ¿?¡!.,:;\t\n")
        project = self._extract_project(stripped)
        context = self._extract_context(stripped)

        if has_pending_task and normalized and not self._looks_like_new_intent(normalized):
            return RoutingDecision(
                IntentKind.CLARIFICATION,
                0.82,
                project=project,
                context=context,
                reason="respuesta compatible con una aclaracion pendiente",
            )

        if not normalized:
            return RoutingDecision(
                IntentKind.QUERY,
                0.97,
                project=project,
                context=context,
                reason="solo contiene texto citado o vacio",
            )

        if self._KNOWLEDGE_RE.search(normalized):
            return RoutingDecision(
                IntentKind.QUERY,
                0.95,
                project=project,
                context=context,
                reason="peticion conceptual o explicativa",
            )

        if self._DESCRIPTIVE_RE.search(normalized):
            return RoutingDecision(
                IntentKind.QUERY,
                0.9,
                project=project,
                context=context,
                reason="descripcion de comportamiento, no una orden",
            )

        is_direct = bool(self._DIRECT_RE.search(normalized) or self._IMPERATIVE_RE.search(normalized))
        is_indirect = bool(self._INDIRECT_RE.search(normalized))
        if is_direct or is_indirect:
            missing: list[str] = []
            if self._VAGUE_RE.search(normalized) and len(normalized.split()) <= 12:
                missing.append("objetivo concreto")
            return RoutingDecision(
                IntentKind.TASK,
                0.98 if is_direct else 0.91,
                project=project,
                context=context,
                reason="solicitud de accion directa" if is_direct else "solicitud de accion indirecta",
                missing_information=tuple(missing),
            )

        if any(root in normalized for root in self._ACTION_ROOTS):
            return RoutingDecision(
                IntentKind.CLARIFICATION,
                0.56,
                project=project,
                context=context,
                reason="posible accion sin formulacion suficientemente clara",
                missing_information=("confirmar si se solicita ejecutar un trabajo",),
            )

        return RoutingDecision(
            IntentKind.QUERY,
            0.86,
            project=project,
            context=context,
            reason="conversacion o consulta sin solicitud de accion",
        )

    def _looks_like_new_intent(self, normalized: str) -> bool:
        return bool(
            self._KNOWLEDGE_RE.search(normalized)
            or self._DIRECT_RE.search(normalized)
            or self._INDIRECT_RE.search(normalized)
        )

    def _extract_project(self, text: str) -> str | None:
        normalized = _normalize(text)
        if re.search(r"(?<!\w)HA(?!\w)", text):
            return "Home Assistant"
        for alias, canonical in sorted(self._KNOWN_PROJECTS.items(), key=lambda item: -len(item[0])):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                return canonical

        quoted = re.search(
            r"proyecto\s+(?:llamado|denominado)?\s*[\"“«]([^\"”»]+)[\"”»]",
            text,
            flags=re.IGNORECASE,
        )
        if quoted:
            return quoted.group(1).strip()

        simple = re.search(
            r"\bproyecto\s+(?:(?:llamado|denominado)\s+)?([A-Za-z0-9_.-]+)",
            text,
            flags=re.IGNORECASE,
        )
        if simple and simple.group(1).lower() not in {"para", "con", "que", "en"}:
            return simple.group(1).strip()
        return None

    def _extract_context(self, text: str) -> str | None:
        path = self._PATH_RE.search(text)
        if path:
            return path.group(0).strip().rstrip(".,;)")
        return None


class AdaptiveClarificationAnalyzer:
    """Pregunta solo cuando una respuesta puede cambiar materialmente el plan."""

    _SOFTWARE_RE = re.compile(
        r"\b(?:codigo|script|bot|api|app|aplicacion|servicio|repositorio|repo|"
        r"funcion|clase|modulo|prueba|test|bug|error|base de datos|frontend|backend|"
        r"autenticacion|oauth|endpoint|interfaz|formulario|dependencia|paquete)\b"
    )
    _GREENFIELD_RE = re.compile(r"\b(?:crea|construye|desarrolla)\s+(?:una?\s+)?(?:app|aplicacion|servicio|bot)\b")
    _TECH_RE = re.compile(r"\b(?:python|javascript|typescript|java|c#|rust|go|react|vue|node|django|fastapi|flask)\b")

    def questions_for(self, request: str, decision: RoutingDecision) -> tuple[str, ...]:
        normalized = _normalize(request)
        questions: list[str] = []

        if "objetivo concreto" in decision.missing_information:
            questions.append("¿Qué componente o comportamiento concreto debo cambiar?")

        if self._SOFTWARE_RE.search(normalized) and not decision.project and not decision.context:
            questions.append("¿En qué proyecto o ruta debo realizar el trabajo?")

        if self._GREENFIELD_RE.search(normalized) and not self._TECH_RE.search(normalized):
            questions.append("¿Qué plataforma o tecnología debe usarse?")

        # Mantiene orden estable y elimina preguntas equivalentes duplicadas.
        return tuple(dict.fromkeys(questions))


class StructuredPlanGenerator:
    SCHEMA_VERSION = 1
    REQUIRED_LIST_FIELDS = (
        "scope",
        "technologies",
        "tests",
        "risks",
        "exclusions",
        "completion_criteria",
    )

    def __init__(self, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts debe ser al menos 1")
        self.max_attempts = max_attempts

    async def generate(
        self,
        request: str,
        *,
        project: str | None,
        context: str | None,
        clarifications: tuple[str, ...],
        provider: PlanningProvider,
    ) -> tuple[StructuredPlan, str]:
        prompt = self._planning_prompt(request, project, context, clarifications)
        errors: list[str] = []
        raw = ""
        for attempt in range(1, self.max_attempts + 1):
            raw = await provider.complete(prompt)
            try:
                return self.parse_and_validate(raw), raw
            except PlanGenerationError as exc:
                errors.append(f"intento {attempt}: {exc}")
                if attempt < self.max_attempts:
                    prompt = self._repair_prompt(raw, str(exc))
        raise PlanGenerationError("; ".join(errors))

    def parse_and_validate(self, raw: str) -> StructuredPlan:
        payload = self._first_json_object(raw)
        if not isinstance(payload, dict):
            raise PlanGenerationError("la respuesta no contiene un objeto JSON")

        objective = self._required_text(payload, "objective")
        professional_prompt = self._required_text(payload, "professional_prompt")
        values = {field: self._required_text_list(payload, field) for field in self.REQUIRED_LIST_FIELDS}

        raw_phases = payload.get("phases")
        if not isinstance(raw_phases, list) or not raw_phases:
            raise PlanGenerationError("phases debe ser una lista no vacia")
        phases: list[PlanPhase] = []
        for index, phase in enumerate(raw_phases, start=1):
            if not isinstance(phase, dict):
                raise PlanGenerationError(f"phases[{index}] debe ser un objeto")
            phases.append(
                PlanPhase(
                    name=self._required_text(phase, "name", prefix=f"phases[{index}]."),
                    objective=self._required_text(phase, "objective", prefix=f"phases[{index}]."),
                    deliverables=self._required_text_list(
                        phase, "deliverables", prefix=f"phases[{index}]."
                    ),
                )
            )

        return StructuredPlan(
            objective=objective,
            professional_prompt=professional_prompt,
            scope=values["scope"],
            technologies=values["technologies"],
            phases=tuple(phases),
            tests=values["tests"],
            risks=values["risks"],
            exclusions=values["exclusions"],
            completion_criteria=values["completion_criteria"],
        )

    @staticmethod
    def plan_hash(plan: StructuredPlan) -> str:
        canonical = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _first_json_object(raw: str) -> object:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", raw):
            try:
                value, _ = decoder.raw_decode(raw[match.start() :])
                return value
            except json.JSONDecodeError:
                continue
        raise PlanGenerationError("no se encontro JSON valido")

    @staticmethod
    def _required_text(payload: dict[str, object], field: str, *, prefix: str = "") -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PlanGenerationError(f"{prefix}{field} debe ser texto no vacio")
        return value.strip()

    @staticmethod
    def _required_text_list(
        payload: dict[str, object], field: str, *, prefix: str = ""
    ) -> tuple[str, ...]:
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            raise PlanGenerationError(f"{prefix}{field} debe ser una lista no vacia")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise PlanGenerationError(f"{prefix}{field} solo admite textos no vacios")
        return tuple(item.strip() for item in value)

    def _planning_prompt(
        self,
        request: str,
        project: str | None,
        context: str | None,
        clarifications: tuple[str, ...],
    ) -> str:
        input_data = {
            "request": request,
            "project": project,
            "context": context,
            "clarifications": list(clarifications),
        }
        return (
            "Actua como arquitecto de software. Convierte la solicitud en un prompt profesional y un "
            "plan ejecutable, sin realizar cambios. Responde EXCLUSIVAMENTE con un objeto JSON valido. "
            "No uses Markdown. Esquema obligatorio: "
            '{"objective":"...","professional_prompt":"...","scope":["..."],'
            '"technologies":["..."],"phases":[{"name":"...","objective":"...",'
            '"deliverables":["..."]}],"tests":["..."],"risks":["..."],'
            '"exclusions":["..."],"completion_criteria":["..."]}. '
            "Incluye pruebas especificas y criterios verificables. Datos de entrada: "
            + json.dumps(input_data, ensure_ascii=False)
        )

    @staticmethod
    def _repair_prompt(raw: str, error: str) -> str:
        return (
            "Tu respuesta anterior no cumple el contrato estructurado. Corrigela y devuelve SOLO el objeto "
            "JSON completo, sin Markdown ni comentarios. Error de validacion: "
            + error
            + "\nRespuesta anterior:\n"
            + raw
        )


class TaskWorkflowStore:
    """Persistencia SQLite con transacciones e idempotencia por mensaje origen."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = threading.RLock()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    source_key TEXT NOT NULL UNIQUE,
                    request_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    project TEXT,
                    context TEXT,
                    status TEXT NOT NULL,
                    missing_information_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_clarifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    source_key TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES task_requests(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    plan_json TEXT NOT NULL,
                    plan_hash TEXT NOT NULL,
                    raw_response TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, version),
                    FOREIGN KEY (task_id) REFERENCES task_requests(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL UNIQUE,
                    plan_id INTEGER NOT NULL UNIQUE,
                    plan_version INTEGER NOT NULL,
                    plan_hash TEXT NOT NULL,
                    approved_by INTEGER NOT NULL,
                    source_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES task_requests(id) ON DELETE CASCADE,
                    FOREIGN KEY (plan_id) REFERENCES task_plans(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS task_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL UNIQUE,
                    plan_id INTEGER NOT NULL UNIQUE,
                    plan_version INTEGER NOT NULL,
                    plan_hash TEXT NOT NULL,
                    requested_by INTEGER NOT NULL,
                    source_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES task_requests(id) ON DELETE CASCADE,
                    FOREIGN KEY (plan_id) REFERENCES task_plans(id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS idx_task_requests_conversation
                    ON task_requests(conversation_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_task_plans_task
                    ON task_plans(task_id, version DESC);
                """
            )

    def create_task(
        self,
        *,
        conversation_id: int,
        source_key: str,
        request_text: str,
        decision: RoutingDecision,
        questions: tuple[str, ...],
    ) -> tuple[TaskRecord, bool]:
        now = _utc_now()
        status = "pending_clarification" if questions else "pending_planning"
        missing = json.dumps(list(questions), ensure_ascii=False)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM task_requests WHERE source_key = ?", (source_key,)
            ).fetchone()
            if existing:
                connection.commit()
                return self._task_from_row(existing), False
            cursor = connection.execute(
                """
                INSERT INTO task_requests (
                    conversation_id, source_key, request_text, confidence, project, context,
                    status, missing_information_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    source_key,
                    request_text,
                    decision.confidence,
                    decision.project,
                    decision.context,
                    status,
                    missing,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM task_requests WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._task_from_row(row), True

    def get_task(self, task_id: int, *, conversation_id: int | None = None) -> TaskRecord | None:
        query = "SELECT * FROM task_requests WHERE id = ?"
        params: tuple[object, ...] = (task_id,)
        if conversation_id is not None:
            query += " AND conversation_id = ?"
            params = (task_id, conversation_id)
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._task_from_row(row) if row else None

    def latest_task(self, conversation_id: int) -> TaskRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_requests WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        return self._task_from_row(row) if row else None

    def add_clarification(self, task_id: int, *, source_key: str, answer: str) -> bool:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT task_id FROM task_clarifications WHERE source_key = ?", (source_key,)
            ).fetchone()
            if existing:
                connection.commit()
                if int(existing["task_id"]) != task_id:
                    raise TaskWorkflowError("el mensaje ya pertenece a otra aclaracion")
                return False
            connection.execute(
                "INSERT INTO task_clarifications (task_id, source_key, answer, created_at) VALUES (?, ?, ?, ?)",
                (task_id, source_key, answer.strip(), now),
            )
            connection.execute(
                "UPDATE task_requests SET status = 'pending_planning', missing_information_json = '[]', "
                "updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            connection.commit()
        return True

    def clarifications(self, task_id: int) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT answer FROM task_clarifications WHERE task_id = ? ORDER BY id", (task_id,)
            ).fetchall()
        return tuple(str(row["answer"]) for row in rows)

    def set_pending_clarification(self, task_id: int, questions: tuple[str, ...]) -> None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE task_requests SET status = 'pending_clarification', "
                "missing_information_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(list(questions), ensure_ascii=False), now, task_id),
            )

    def mark_planning_failed(self, task_id: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE task_requests SET status = 'planning_failed', updated_at = ? WHERE id = ?",
                (_utc_now(), task_id),
            )

    def create_plan(self, task_id: int, plan: StructuredPlan, raw_response: str) -> PlanRecord:
        now = _utc_now()
        plan_json = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True)
        plan_hash = StructuredPlanGenerator.plan_hash(plan)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute("SELECT status FROM task_requests WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise TaskWorkflowError("tarea inexistente")
            if task["status"] in {"approved", "execution_started", "execution_completed"}:
                raise TaskWorkflowError("la tarea ya esta aprobada o en ejecucion")
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM task_plans WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            version = int(row["version"]) + 1
            connection.execute(
                "UPDATE task_plans SET status = 'superseded' "
                "WHERE task_id = ? AND status = 'pending_approval'",
                (task_id,),
            )
            cursor = connection.execute(
                """
                INSERT INTO task_plans (
                    task_id, version, status, schema_version, plan_json, plan_hash,
                    raw_response, created_at
                ) VALUES (?, ?, 'pending_approval', ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    version,
                    StructuredPlanGenerator.SCHEMA_VERSION,
                    plan_json,
                    plan_hash,
                    raw_response,
                    now,
                ),
            )
            connection.execute(
                "UPDATE task_requests SET status = 'pending_approval', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            row = connection.execute("SELECT * FROM task_plans WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.commit()
        return self._plan_from_row(row)

    def latest_plan(self, task_id: int) -> PlanRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_plans WHERE task_id = ? ORDER BY version DESC LIMIT 1", (task_id,)
            ).fetchone()
        return self._plan_from_row(row) if row else None

    def approve(
        self,
        task_id: int,
        *,
        conversation_id: int,
        version: int,
        plan_hash: str,
        approved_by: int,
        source_key: str,
    ) -> ApprovalRecord:
        _validate_approval_input(
            task_id,
            conversation_id=conversation_id,
            version=version,
            plan_hash=plan_hash,
            approved_by=approved_by,
            source_key=source_key,
        )
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_source = connection.execute(
                "SELECT * FROM task_approvals WHERE source_key = ?", (source_key,)
            ).fetchone()
            if existing_source:
                if (
                    int(existing_source["task_id"]) != task_id
                    or int(existing_source["plan_version"]) != version
                    or str(existing_source["plan_hash"]) != plan_hash
                    or int(existing_source["approved_by"]) != approved_by
                ):
                    raise ApprovalError("la clave idempotente ya pertenece a otra aprobacion")
                existing_task = connection.execute(
                    "SELECT id FROM task_requests WHERE id = ? AND conversation_id = ?",
                    (task_id, conversation_id),
                ).fetchone()
                if not existing_task:
                    raise ApprovalError("no existe esa tarea en esta conversacion")
                connection.commit()
                return self._approval_from_row(existing_source)

            task = connection.execute(
                "SELECT id FROM task_requests WHERE id = ? AND conversation_id = ?",
                (task_id, conversation_id),
            ).fetchone()
            if not task:
                raise ApprovalError("no existe esa tarea en esta conversacion")

            latest = connection.execute(
                "SELECT * FROM task_plans WHERE task_id = ? ORDER BY version DESC LIMIT 1", (task_id,)
            ).fetchone()
            if not latest:
                raise ApprovalError("la tarea aun no tiene un plan")
            if int(latest["version"]) != version or str(latest["plan_hash"]) != plan_hash:
                raise ApprovalError("solo se puede aprobar la ultima version exacta del plan")
            if str(latest["status"]) != "pending_approval":
                raise ApprovalError("el plan no esta pendiente de aprobacion")

            cursor = connection.execute(
                """
                INSERT INTO task_approvals (
                    task_id, plan_id, plan_version, plan_hash, approved_by, source_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, int(latest["id"]), version, plan_hash, approved_by, source_key, now),
            )
            connection.execute("UPDATE task_plans SET status = 'approved' WHERE id = ?", (latest["id"],))
            connection.execute(
                "UPDATE task_requests SET status = 'approved', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            row = connection.execute(
                "SELECT * FROM task_approvals WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._approval_from_row(row)

    def begin_execution(
        self,
        task_id: int,
        *,
        version: int,
        plan_hash: str,
        requested_by: int,
        source_key: str,
    ) -> tuple[ExecutionRecord, bool]:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_source = connection.execute(
                "SELECT * FROM task_executions WHERE source_key = ?", (source_key,)
            ).fetchone()
            if existing_source:
                if (
                    int(existing_source["task_id"]) != task_id
                    or int(existing_source["plan_version"]) != version
                    or str(existing_source["plan_hash"]) != plan_hash
                    or int(existing_source["requested_by"]) != requested_by
                ):
                    raise ExecutionBlockedError(
                        "ejecucion bloqueada: la clave idempotente pertenece a otra solicitud"
                    )
                connection.commit()
                return self._execution_from_row(existing_source), False

            latest = connection.execute(
                "SELECT * FROM task_plans WHERE task_id = ? ORDER BY version DESC LIMIT 1", (task_id,)
            ).fetchone()
            approval = connection.execute(
                "SELECT * FROM task_approvals WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not latest or not approval:
                raise ExecutionBlockedError("ejecucion bloqueada: falta una aprobacion explicita")
            if (
                int(latest["version"]) != version
                or str(latest["plan_hash"]) != plan_hash
                or int(approval["plan_id"]) != int(latest["id"])
                or int(approval["plan_version"]) != version
                or str(approval["plan_hash"]) != plan_hash
            ):
                raise ExecutionBlockedError("ejecucion bloqueada: la aprobacion no corresponde al ultimo plan")

            existing_task = connection.execute(
                "SELECT * FROM task_executions WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing_task:
                connection.commit()
                return self._execution_from_row(existing_task), False

            cursor = connection.execute(
                """
                INSERT INTO task_executions (
                    task_id, plan_id, plan_version, plan_hash, requested_by,
                    source_key, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'started', ?, ?)
                """,
                (
                    task_id,
                    int(latest["id"]),
                    version,
                    plan_hash,
                    requested_by,
                    source_key,
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE task_requests SET status = 'execution_started', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            row = connection.execute(
                "SELECT * FROM task_executions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._execution_from_row(row), True

    def complete_execution(self, execution_id: int, *, success: bool) -> None:
        state = "completed" if success else "failed"
        task_status = "execution_completed" if success else "execution_failed"
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT task_id FROM task_executions WHERE id = ?", (execution_id,)
            ).fetchone()
            if not row:
                raise TaskWorkflowError("ejecucion inexistente")
            connection.execute(
                "UPDATE task_executions SET state = ?, updated_at = ? WHERE id = ?",
                (state, now, execution_id),
            )
            connection.execute(
                "UPDATE task_requests SET status = ?, updated_at = ? WHERE id = ?",
                (task_status, now, int(row["task_id"])),
            )
            connection.commit()

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=int(row["id"]),
            conversation_id=int(row["conversation_id"]),
            source_key=str(row["source_key"]),
            request_text=str(row["request_text"]),
            confidence=float(row["confidence"]),
            project=str(row["project"]) if row["project"] is not None else None,
            context=str(row["context"]) if row["context"] is not None else None,
            status=str(row["status"]),
            missing_information=tuple(json.loads(str(row["missing_information_json"]))),
        )

    @staticmethod
    def _plan_from_row(row: sqlite3.Row) -> PlanRecord:
        payload = json.loads(str(row["plan_json"]))
        plan = StructuredPlanGenerator().parse_and_validate(json.dumps(payload, ensure_ascii=False))
        return PlanRecord(
            id=int(row["id"]),
            task_id=int(row["task_id"]),
            version=int(row["version"]),
            status=str(row["status"]),
            plan=plan,
            plan_hash=str(row["plan_hash"]),
            raw_response=str(row["raw_response"]),
        )

    @staticmethod
    def _approval_from_row(row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(
            id=int(row["id"]),
            task_id=int(row["task_id"]),
            plan_id=int(row["plan_id"]),
            plan_version=int(row["plan_version"]),
            plan_hash=str(row["plan_hash"]),
            approved_by=int(row["approved_by"]),
        )

    @staticmethod
    def _execution_from_row(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            id=int(row["id"]),
            task_id=int(row["task_id"]),
            plan_id=int(row["plan_id"]),
            plan_version=int(row["plan_version"]),
            plan_hash=str(row["plan_hash"]),
            requested_by=int(row["requested_by"]),
            state=str(row["state"]),
        )


class TaskWorkflowService:
    """Orquesta el flujo, manteniendo el modelo fuera de la persistencia."""

    def __init__(
        self,
        store: TaskWorkflowStore,
        *,
        classifier: TaskIntentClassifier | None = None,
        clarification_analyzer: AdaptiveClarificationAnalyzer | None = None,
        plan_generator: StructuredPlanGenerator | None = None,
    ) -> None:
        self.store = store
        self.classifier = classifier or TaskIntentClassifier()
        self.clarification_analyzer = clarification_analyzer or AdaptiveClarificationAnalyzer()
        self.plan_generator = plan_generator or StructuredPlanGenerator()

    def classify(self, text: str, *, has_pending_task: bool = False) -> RoutingDecision:
        return self.classifier.classify(text, has_pending_task=has_pending_task)

    async def submit(
        self,
        *,
        conversation_id: int,
        source_key: str,
        request_text: str,
        provider: PlanningProvider,
    ) -> WorkflowOutcome:
        decision = self.classify(request_text)
        if decision.kind is not IntentKind.TASK:
            return WorkflowOutcome(decision=decision)

        questions = self.clarification_analyzer.questions_for(request_text, decision)
        task, created = self.store.create_task(
            conversation_id=conversation_id,
            source_key=source_key,
            request_text=request_text,
            decision=decision,
            questions=questions,
        )
        if not created:
            return WorkflowOutcome(
                decision=decision,
                task=task,
                plan=self.store.latest_plan(task.id),
                questions=task.missing_information,
                created=False,
            )
        if questions:
            return WorkflowOutcome(
                decision=decision, task=task, questions=questions, created=True
            )

        plan = await self._generate_plan(task, provider)
        return WorkflowOutcome(decision=decision, task=task, plan=plan, created=True)

    async def clarify(
        self,
        task_id: int,
        *,
        conversation_id: int,
        source_key: str,
        answer: str,
        provider: PlanningProvider,
    ) -> WorkflowOutcome:
        task = self.store.get_task(task_id, conversation_id=conversation_id)
        if not task:
            raise TaskWorkflowError("no existe esa tarea en esta conversacion")
        if task.status not in {"pending_clarification", "pending_approval", "planning_failed"}:
            raise TaskWorkflowError("la tarea ya no admite aclaraciones")

        added = self.store.add_clarification(task_id, source_key=source_key, answer=answer)
        decision = self.classifier.classify(task.request_text)
        if not added:
            refreshed = self.store.get_task(task_id, conversation_id=conversation_id)
            return WorkflowOutcome(
                decision=decision,
                task=refreshed,
                plan=self.store.latest_plan(task_id),
                questions=refreshed.missing_information if refreshed else (),
                created=False,
            )

        all_clarifications = self.store.clarifications(task_id)
        combined = task.request_text + "\n" + "\n".join(
            f"Aclaracion: {item}" for item in all_clarifications
        )
        combined_decision = self.classifier.classify(combined)
        questions = self.clarification_analyzer.questions_for(combined, combined_decision)
        if questions:
            self.store.set_pending_clarification(task_id, questions)
            refreshed = self.store.get_task(task_id, conversation_id=conversation_id)
            return WorkflowOutcome(decision=decision, task=refreshed, questions=questions)

        refreshed = self.store.get_task(task_id, conversation_id=conversation_id)
        assert refreshed is not None
        plan = await self._generate_plan(refreshed, provider)
        return WorkflowOutcome(decision=decision, task=refreshed, plan=plan, created=True)

    def approve(
        self,
        task_id: int,
        *,
        conversation_id: int,
        version: int,
        plan_hash: str,
        approved_by: int,
        source_key: str,
    ) -> ApprovalRecord:
        _validate_approval_input(
            task_id,
            conversation_id=conversation_id,
            version=version,
            plan_hash=plan_hash,
            approved_by=approved_by,
            source_key=source_key,
        )
        return self.store.approve(
            task_id,
            conversation_id=conversation_id,
            version=version,
            plan_hash=plan_hash,
            approved_by=approved_by,
            source_key=source_key,
        )

    async def execute(
        self,
        task_id: int,
        *,
        conversation_id: int,
        version: int,
        plan_hash: str,
        requested_by: int,
        source_key: str,
        executor: Callable[[PlanRecord], Awaitable[None]],
    ) -> ExecutionRecord:
        if not self.store.get_task(task_id, conversation_id=conversation_id):
            raise ExecutionBlockedError("ejecucion bloqueada: tarea desconocida")
        execution, created = self.store.begin_execution(
            task_id,
            version=version,
            plan_hash=plan_hash,
            requested_by=requested_by,
            source_key=source_key,
        )
        if not created:
            return execution
        plan = self.store.latest_plan(task_id)
        assert plan is not None
        try:
            await executor(plan)
        except Exception:
            self.store.complete_execution(execution.id, success=False)
            raise
        self.store.complete_execution(execution.id, success=True)
        refreshed, _ = self.store.begin_execution(
            task_id,
            version=version,
            plan_hash=plan_hash,
            requested_by=requested_by,
            source_key=source_key,
        )
        return refreshed

    async def _generate_plan(self, task: TaskRecord, provider: PlanningProvider) -> PlanRecord:
        try:
            plan, raw = await self.plan_generator.generate(
                task.request_text,
                project=task.project,
                context=task.context,
                clarifications=self.store.clarifications(task.id),
                provider=provider,
            )
        except PlanGenerationError:
            self.store.mark_planning_failed(task.id)
            raise
        return self.store.create_plan(task.id, plan, raw)


def format_plan(plan_record: PlanRecord) -> str:
    plan = plan_record.plan
    phases = "\n".join(
        f"  {index}. {phase.name}: {phase.objective}\n"
        + "\n".join(f"     - {item}" for item in phase.deliverables)
        for index, phase in enumerate(plan.phases, start=1)
    )
    scope = "\n".join(f"  - {item}" for item in plan.scope)
    technologies = "\n".join(f"  - {item}" for item in plan.technologies)
    tests = "\n".join(f"  - {item}" for item in plan.tests)
    risks = "\n".join(f"  - {item}" for item in plan.risks)
    exclusions = "\n".join(f"  - {item}" for item in plan.exclusions)
    criteria = "\n".join(f"  - {item}" for item in plan.completion_criteria)
    return (
        f"Plan de tarea #{plan_record.task_id} · v{plan_record.version}\n"
        f"Huella: {plan_record.plan_hash}\n\n"
        f"Objetivo: {plan.objective}\n\n"
        f"Prompt profesional:\n{plan.professional_prompt}\n\n"
        f"Alcance:\n{scope}\n\n"
        f"Tecnologias:\n{technologies}\n\n"
        f"Fases:\n{phases}\n\n"
        f"Pruebas:\n{tests}\n\n"
        f"Riesgos:\n{risks}\n\n"
        f"Exclusiones:\n{exclusions}\n\n"
        f"Criterios de finalizacion:\n{criteria}\n\n"
        "Para aprobar exactamente esta version:\n"
        f"/aprobar_tarea {plan_record.task_id} {plan_record.version} {plan_record.plan_hash}"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_executor_once(
    service: TaskWorkflowService,
    task_id: int,
    *,
    conversation_id: int,
    version: int,
    plan_hash: str,
    requested_by: int,
    source_key: str,
    executor: Callable[[PlanRecord], Awaitable[None]],
) -> ExecutionRecord:
    """Punto explicito para integradores; nunca se llama durante la planificacion."""

    return await service.execute(
        task_id,
        conversation_id=conversation_id,
        version=version,
        plan_hash=plan_hash,
        requested_by=requested_by,
        source_key=source_key,
        executor=executor,
    )


__all__ = [
    "AdaptiveClarificationAnalyzer",
    "ApprovalError",
    "CallablePlanningProvider",
    "ExecutionBlockedError",
    "IntentKind",
    "PlanGenerationError",
    "PlanRecord",
    "RoutingDecision",
    "StructuredPlan",
    "StructuredPlanGenerator",
    "TaskIntentClassifier",
    "TaskWorkflowError",
    "TaskWorkflowService",
    "TaskWorkflowStore",
    "WorkflowOutcome",
    "format_plan",
    "run_executor_once",
]
