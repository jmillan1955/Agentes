import sqlite3

import pytest

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskApprovalRepository,
    TaskExecutionRepository,
    TaskPlanRepository,
    TaskRepository,
    TaskExecutionAttemptRepository,
    TaskExecutionStepRepository,
)
from app.execution import (
    ExecutionStatus,
    InvalidExecutionTransitionError,
    ExecutionAttemptStatus,
    ExecutionStepStatus,
)
from app.tasks import TaskStatus


def prepare_approved_task(
    database: ContextDatabase,
):
    project = ProjectRepository(
        database
    ).save(
        name="Proyecto temporal",
        root_path="ruta-temporal",
    )

    session = SessionRepository(
        database
    ).get_or_create_active(
        project_id=project.id,
        channel="telegram",
        user_id="123456",
        conversation_id="conversacion",
    )

    task_repository = TaskRepository(
        database
    )

    task = task_repository.create(
        project_id=project.id,
        session_id=session.id,
        source_message_id="mensaje-tarea",
        title="Crear proyecto temporal",
        description=(
            "Tarea usada solamente "
            "para pruebas"
        ),
        target_project_name=(
            "proyecto_temporal"
        ),
    )

    plan = TaskPlanRepository(
        database
    ).create(
        task_id=task.id,
        objective="Probar la ejecucion",
        scope=("Crear archivos temporales",),
        technologies=("Python",),
        interfaces=("Consola",),
        inputs=("Plan aprobado",),
        outputs=("Resultado temporal",),
        data_entities=("Ejecucion",),
        business_rules=(
            "No escribir fuera del workspace",
        ),
        phases=("Preparar", "Ejecutar"),
        tests=("Verificar el resultado",),
        deployment=("No aplica",),
        excluded_items=(
            "No usar proyectos reales",
        ),
        completion_criteria=(
            "Ejecucion controlada",
        ),
    )

    task_repository.set_plan(
        task_id=task.id,
        plan=plan.phases,
    )

    approval = TaskApprovalRepository(
        database
    ).approve(
        task_id=task.id,
        plan_id=plan.id,
        plan_version=plan.version,
        authorized_user_id="123456",
        authorization_message_id=(
            "telegram:aprobar:1"
        ),
        channel="telegram",
    )

    return task, plan, approval


def prepare_execution(
    database: ContextDatabase,
):
    task, plan, approval = (
        prepare_approved_task(database)
    )

    repository = TaskExecutionRepository(
        database
    )

    execution = repository.prepare(
        task_id=task.id,
        plan_id=plan.id,
        approval_id=approval.id,
        workspace_path="workspace-temporal",
        requested_by_user_id="123456",
        request_message_id=(
            "telegram:ejecutar:transicion"
        ),
        channel="telegram",
    )

    return repository, execution


def test_prepares_execution_for_approved_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan, approval = (
            prepare_approved_task(database)
        )

        repository = TaskExecutionRepository(
            database
        )

        execution = repository.prepare(
            task_id=task.id,
            plan_id=plan.id,
            approval_id=approval.id,
            workspace_path="workspace-temporal",
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:ejecutar:1"
            ),
            channel="telegram",
        )

        assert execution.id > 0
        assert execution.task_id == task.id
        assert execution.plan_id == plan.id
        assert (
            execution.approval_id
            == approval.id
        )
        assert (
            execution.status
            == ExecutionStatus.PREPARED
        )
        assert execution.attempt_count == 0
        assert execution.started_at is None
        assert execution.finished_at is None

        stored = repository.get_by_id(
            execution.id
        )

        assert stored == execution

        stored_task = TaskRepository(
            database
        ).get_by_id(task.id)

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.APPROVED
        )


def test_prepare_is_idempotent() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan, approval = (
            prepare_approved_task(database)
        )

        repository = TaskExecutionRepository(
            database
        )

        first = repository.prepare(
            task_id=task.id,
            plan_id=plan.id,
            approval_id=approval.id,
            workspace_path="workspace-temporal",
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:ejecutar:2"
            ),
            channel="telegram",
        )

        repeated = repository.prepare(
            task_id=task.id,
            plan_id=plan.id,
            approval_id=approval.id,
            workspace_path="workspace-temporal",
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:ejecutar:3"
            ),
            channel="telegram",
        )

        assert repeated == first

        count = database.connection.execute(
            """
            SELECT COUNT(*)
            FROM task_executions
            WHERE task_id = ?
            """,
            (task.id,),
        ).fetchone()[0]

        assert count == 1


def test_rejects_unauthorized_user() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan, approval = (
            prepare_approved_task(database)
        )

        repository = TaskExecutionRepository(
            database
        )

        with pytest.raises(
            ValueError,
            match=(
                "El usuario no esta autorizado"
            ),
        ):
            repository.prepare(
                task_id=task.id,
                plan_id=plan.id,
                approval_id=approval.id,
                workspace_path=(
                    "workspace-temporal"
                ),
                requested_by_user_id=(
                    "usuario-distinto"
                ),
                request_message_id=(
                    "telegram:ejecutar:4"
                ),
                channel="telegram",
            )

        assert (
            repository.get_by_task_id(
                task.id
            )
            is None
        )


@pytest.mark.parametrize(
    ("column", "invalid_value"),
    (
        ("status", "invalid"),
        ("attempt_count", -1),
    ),
)
def test_database_rejects_invalid_values(
    column: str,
    invalid_value: object,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        task, plan, approval = (
            prepare_approved_task(database)
        )

        repository = TaskExecutionRepository(
            database
        )

        execution = repository.prepare(
            task_id=task.id,
            plan_id=plan.id,
            approval_id=approval.id,
            workspace_path="workspace-temporal",
            requested_by_user_id="123456",
            request_message_id=(
                "telegram:ejecutar:5"
            ),
            channel="telegram",
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            database.connection.execute(
                f"""
                UPDATE task_executions
                SET {column} = ?
                WHERE id = ?
                """,
                (
                    invalid_value,
                    execution.id,
                ),
            )


def test_starts_prepared_execution() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        running = repository.start(
            execution.id
        )

        assert (
            running.status
            == ExecutionStatus.RUNNING
        )
        assert running.attempt_count == 1
        assert running.started_at is not None
        assert running.finished_at is None
        assert running.last_error is None
        stored_task = TaskRepository(
            database
        ).get_by_id(
            running.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.IN_PROGRESS
        )
        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                running.id
            )
        )

        assert attempt is not None
        assert attempt.attempt_number == 1
        assert (
            attempt.status
            == ExecutionAttemptStatus.RUNNING
        )
        assert attempt.finished_at is None

def test_retries_failed_execution() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        running = repository.start(
            execution.id
        )

        attempt_before_failure = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                running.id
            )
        )

        assert running.attempt_count == 1
        assert attempt_before_failure is not None
        assert (
            attempt_before_failure.execution_id
            == running.id
        )
        assert (
            attempt_before_failure.attempt_number
            == running.attempt_count
        )
        assert (
            attempt_before_failure.status
            == ExecutionAttemptStatus.RUNNING
        )

        failed = repository.transition(
            execution_id=running.id,
            target_status=(
                ExecutionStatus.FAILED
            ),
            last_error="Fallo temporal",
        )

        assert (
            failed.status
            == ExecutionStatus.FAILED
        )
        assert (
            failed.last_error
            == "Fallo temporal"
        )
        assert failed.finished_at is not None

        retried = repository.start(
            failed.id
        )

        assert (
            retried.status
            == ExecutionStatus.RUNNING
        )
        assert retried.attempt_count == 2
        assert retried.last_error is None
        assert retried.finished_at is None

        stored_task = TaskRepository(
            database
        ).get_by_id(
            retried.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.IN_PROGRESS
        )

        attempts = (
            TaskExecutionAttemptRepository(
                database
            ).list_by_execution(
                retried.id
            )
        )

        assert len(attempts) == 2
        assert attempts[0].attempt_number == 1
        assert (
            attempts[0].status
            == ExecutionAttemptStatus.FAILED
        )
        assert (
            attempts[0].error_message
            == "Fallo temporal"
        )
        assert (
            attempts[0].finished_at
            is not None
        )
        assert attempts[1].attempt_number == 2
        assert (
            attempts[1].status
            == ExecutionAttemptStatus.RUNNING
        )

def test_completes_running_execution() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        running = repository.start(
            execution.id
        )

        completed = repository.complete(
            running.id
        )

        assert (
            completed.status
            == ExecutionStatus.COMPLETED
        )
        assert completed.finished_at is not None
        assert completed.is_terminal is True

        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                completed.id
            )
        )

        assert attempt is not None
        assert (
            attempt.status
            == ExecutionAttemptStatus.COMPLETED
        )
        assert attempt.finished_at is not None
        assert attempt.exit_code == 0
        assert attempt.error_message is None


        with pytest.raises(
            InvalidExecutionTransitionError
        ):
            repository.transition(
                execution_id=completed.id,
                target_status=(
                    ExecutionStatus.RUNNING
                ),
            )
        stored_task = TaskRepository(
            database
        ).get_by_id(
            completed.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.COMPLETED
        )
        assert (
            stored_task.completed_at
            is not None
        )

def test_cancels_prepared_execution() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        cancelled = repository.cancel(
            execution.id
        )

        assert (
            cancelled.status
            == ExecutionStatus.CANCELLED
        )
        assert cancelled.attempt_count == 0
        assert cancelled.started_at is None
        assert cancelled.finished_at is not None
        stored_task = TaskRepository(
            database
        ).get_by_id(
            cancelled.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.CANCELLED
        )

        repeated = repository.cancel(
            cancelled.id
        )

        assert repeated == cancelled

def test_finalizes_failed_task() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        running = repository.start(
            execution.id
        )

        failed = repository.transition(
            execution_id=running.id,
            target_status=(
                ExecutionStatus.FAILED
            ),
            last_error="Fallo definitivo",
        )

        finalized = (
            repository.finalize_failure(
                failed.id
            )
        )

        assert (
            finalized.status
            == ExecutionStatus.FAILED
        )
        assert (
            finalized.last_error
            == "Fallo definitivo"
        )

        stored_task = TaskRepository(
            database
        ).get_by_id(
            finalized.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.FAILED
        )
        assert (
            stored_task.completed_at
            is not None
        )

        repeated = (
            repository.finalize_failure(
                finalized.id
            )
        )

        assert repeated == finalized

        with pytest.raises(
            ValueError,
            match="no permite iniciar",
        ):
            repository.start(
                finalized.id
            )

def test_cancels_running_attempt() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository, execution = (
            prepare_execution(database)
        )

        running = repository.start(
            execution.id
        )

        cancelled = repository.cancel(
            running.id
        )

        assert (
            cancelled.status
            == ExecutionStatus.CANCELLED
        )
        assert cancelled.finished_at is not None

        stored_task = TaskRepository(
            database
        ).get_by_id(
            cancelled.task_id
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.CANCELLED
        )

        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                cancelled.id
            )
        )

        assert attempt is not None
        assert (
            attempt.status
            == ExecutionAttemptStatus.CANCELLED
        )
        assert attempt.finished_at is not None

def test_creates_auditable_steps() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_repository, execution = (
            prepare_execution(database)
        )

        running = (
            execution_repository.start(
                execution.id
            )
        )

        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                running.id
            )
        )

        assert attempt is not None

        step_repository = (
            TaskExecutionStepRepository(
                database
            )
        )

        first = step_repository.create(
            attempt_id=attempt.id,
            step_number=1,
            name="Crear estructura",
            action_type="filesystem",
        )

        repeated = step_repository.create(
            attempt_id=attempt.id,
            step_number=1,
            name="Crear estructura",
            action_type="filesystem",
        )

        second = step_repository.create(
            attempt_id=attempt.id,
            step_number=2,
            name="Ejecutar pruebas",
            action_type="test",
        )

        assert repeated == first
        assert (
            first.status
            == ExecutionStepStatus.PENDING
        )
        assert (
            second.status
            == ExecutionStepStatus.PENDING
        )

        steps = (
            step_repository.list_by_attempt(
                attempt.id
            )
        )

        assert steps == (
            first,
            second,
        )

        started = step_repository.start(
            first.id
        )

        assert (
            started.status
            == ExecutionStepStatus.RUNNING
        )
        assert started.started_at is not None
        assert started.finished_at is None

        completed_step = (
            step_repository.complete(
                step_id=started.id,
                stdout_text=(
                    "Estructura creada"
                ),
            )
        )

        assert (
            completed_step.status
            == ExecutionStepStatus.COMPLETED
        )
        assert (
            completed_step.stdout_text
            == "Estructura creada"
        )
        assert completed_step.exit_code == 0
        assert (
            completed_step.finished_at
            is not None
        )
        assert completed_step.is_terminal

def test_rejects_step_for_finished_attempt() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_repository, execution = (
            prepare_execution(database)
        )

        running = (
            execution_repository.start(
                execution.id
            )
        )

        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                running.id
            )
        )

        assert attempt is not None

        execution_repository.complete(
            running.id
        )

        step_repository = (
            TaskExecutionStepRepository(
                database
            )
        )

        with pytest.raises(
            ValueError,
            match="intento activo",
        ):
            step_repository.create(
                attempt_id=attempt.id,
                step_number=1,
                name="Paso tardio",
                action_type="test",
            )

def test_records_failed_step() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        execution_repository, execution = (
            prepare_execution(database)
        )

        running = (
            execution_repository.start(
                execution.id
            )
        )

        attempt = (
            TaskExecutionAttemptRepository(
                database
            ).get_current(
                running.id
            )
        )

        assert attempt is not None

        step_repository = (
            TaskExecutionStepRepository(
                database
            )
        )

        pending = step_repository.create(
            attempt_id=attempt.id,
            step_number=1,
            name="Ejecutar pruebas",
            action_type="test",
        )

        started = step_repository.start(
            pending.id
        )

        failed = step_repository.fail(
            step_id=started.id,
            error_message=(
                "Las pruebas han fallado"
            ),
            exit_code=1,
            stderr_text="1 failed",
        )

        assert (
            failed.status
            == ExecutionStepStatus.FAILED
        )
        assert failed.exit_code == 1
        assert failed.stderr_text == "1 failed"
        assert (
            failed.error_message
            == "Las pruebas han fallado"
        )
        assert failed.finished_at is not None
        assert failed.is_terminal