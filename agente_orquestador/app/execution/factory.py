from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.context import (
    ContextDatabase,
    TaskApprovalRepository,
    TaskExecutionAttemptRepository,
    TaskExecutionRepository,
    TaskExecutionStepRepository,
    TaskRepository,
)
from app.execution.filesystem_executor import (
    SafeFilesystemExecutor,
)
from app.execution.http_sandbox_backend import (
    HttpSandboxBackend,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.runner import (
    ExecutionRunner,
)
from app.execution.sandbox_executor import (
    SafeSandboxExecutor,
)
from app.execution.service import (
    ExecutionPreparationService,
)
from app.execution.workspace import (
    WorkspacePolicy,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)
from app.execution.query import (
    ExecutionQueryService,
)

@dataclass(frozen=True, slots=True)
class ExecutionRuntime:
    preparation_service: (
        ExecutionPreparationService
    )
    query_service: ExecutionQueryService
    runner: ExecutionRunner
    sandbox_enabled: bool


def create_execution_runtime(
    database: ContextDatabase,
    execution_workspace_root: Path,
    protected_project_root: Path,
    sandbox_gateway_url: str | None,
    sandbox_gateway_token: str | None,
    sandbox_gateway_timeout_seconds: float,
) -> ExecutionRuntime:
    if bool(
        sandbox_gateway_url
    ) != bool(
        sandbox_gateway_token
    ):
        raise ValueError(
            "La URL y el token del gateway "
            "deben configurarse juntos"
        )

    workspace_policy = WorkspacePolicy(
        allowed_root=execution_workspace_root,
        protected_paths=(
            protected_project_root,
        ),
    )

    limits = ExecutionLimits()

    execution_repository = (
        TaskExecutionRepository(
            database
        )
    )

    attempt_repository = (
        TaskExecutionAttemptRepository(
            database
        )
    )

    step_repository = (
        TaskExecutionStepRepository(
            database
        )
    )

    query_service = ExecutionQueryService(
        execution_repository=(
            execution_repository
        ),
        attempt_repository=(
            attempt_repository
        ),
        step_repository=step_repository,
    )

    filesystem_executor = (
        SafeFilesystemExecutor(
            workspace_policy=workspace_policy,
            limits=limits,
        )
    )

    sandbox_executor = None

    if (
        sandbox_gateway_url is not None
        and sandbox_gateway_token is not None
    ):
        backend = HttpSandboxBackend(
            gateway_url=sandbox_gateway_url,
            auth_token=sandbox_gateway_token,
            packager=WorkspacePackager(),
            timeout_seconds=(
                sandbox_gateway_timeout_seconds
            ),
        )

        sandbox_executor = (
            SafeSandboxExecutor(
                backend=backend,
                limits=limits,
            )
        )

    preparation_service = (
        ExecutionPreparationService(
            task_repository=TaskRepository(
                database
            ),
            approval_repository=(
                TaskApprovalRepository(
                    database
                )
            ),
            execution_repository=(
                execution_repository
            ),
            workspace_policy=(
                workspace_policy
            ),
        )
    )

    runner = ExecutionRunner(
        execution_repository=(
            execution_repository
        ),
        attempt_repository=(
            attempt_repository
        ),
        step_repository=step_repository,
        filesystem_executor=(
            filesystem_executor
        ),
        limits=limits,
        sandbox_executor=sandbox_executor,
    )

    return ExecutionRuntime(
        preparation_service=(
            preparation_service
        ),
        query_service=query_service,
        runner=runner,
        sandbox_enabled=(
            sandbox_executor is not None
        ),
    )