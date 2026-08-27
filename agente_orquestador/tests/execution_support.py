from dataclasses import dataclass
from pathlib import Path

from app.context import (
    ContextDatabase,
    ProjectRepository,
    SessionRepository,
    TaskApprovalRepository,
    TaskExecutionAttemptRepository,
    TaskExecutionRepository,
    TaskExecutionStepRepository,
    TaskPlanRepository,
    TaskRepository,
)
from app.execution.models import (
    TaskExecution,
)


@dataclass(frozen=True, slots=True)
class ExecutionTestContext:
    execution: TaskExecution
    execution_repository: (
        TaskExecutionRepository
    )
    attempt_repository: (
        TaskExecutionAttemptRepository
    )
    step_repository: (
        TaskExecutionStepRepository
    )
    task_repository: TaskRepository


def prepare_execution_context(
    database: ContextDatabase,
    workspace_path: Path,
) -> ExecutionTestContext:
    project = ProjectRepository(
        database
    ).save(
        name="Proyecto runner temporal",
        root_path=str(workspace_path),
    )

    session = SessionRepository(
        database
    ).get_or_create_active(
        project_id=project.id,
        channel="test",
        user_id="123456",
        conversation_id="runner-temporal",
    )

    task_repository = TaskRepository(
        database
    )

    task = task_repository.create(
        project_id=project.id,
        session_id=session.id,
        source_message_id="runner-tarea-1",
        title="Crear proyecto temporal",
        description=(
            "Probar el ejecutor seguro"
        ),
        target_project_name="temporal",
    )

    plan = TaskPlanRepository(
        database
    ).create(
        task_id=task.id,
        objective=(
            "Crear una estructura temporal"
        ),
        scope=("Crear archivos temporales",),
        technologies=("Python",),
        interfaces=("Sistema de archivos",),
        inputs=("Acciones autorizadas",),
        outputs=("Proyecto temporal",),
        data_entities=("Ejecucion",),
        business_rules=(
            "No salir del workspace",
        ),
        phases=(
            "Crear workspace",
            "Crear directorio",
            "Crear archivo",
        ),
        tests=("Verificar archivos",),
        deployment=("No aplica",),
        excluded_items=(
            "No ejecutar proyectos reales",
        ),
        completion_criteria=(
            "Auditoria completa",
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
            "runner-aprobacion-1"
        ),
        channel="test",
    )

    execution_repository = (
        TaskExecutionRepository(database)
    )

    execution = (
        execution_repository.prepare(
            task_id=task.id,
            plan_id=plan.id,
            approval_id=approval.id,
            workspace_path=str(
                workspace_path.resolve()
            ),
            requested_by_user_id="123456",
            request_message_id=(
                "runner-ejecucion-1"
            ),
            channel="test",
        )
    )

    return ExecutionTestContext(
        execution=execution,
        execution_repository=(
            execution_repository
        ),
        attempt_repository=(
            TaskExecutionAttemptRepository(
                database
            )
        ),
        step_repository=(
            TaskExecutionStepRepository(
                database
            )
        ),
        task_repository=task_repository,
    )