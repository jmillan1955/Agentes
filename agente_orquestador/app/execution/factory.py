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
    TaskExecutionManifestRepository,
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
from app.execution.manifest_service import (
    ExecutionManifestService,
)
from app.execution.action_generator import (
    ExecutionActionGenerator,
)
from app.providers.base import (
    LanguageProvider,
)
from app.execution.start_service import (
    ExecutionStartService,
)
from app.execution.split_action_generator import (
    SplitExecutionActionGenerator,
)
@dataclass(frozen=True, slots=True)
class ExecutionRuntime:
    preparation_service: (
        ExecutionPreparationService
    )
    query_service: ExecutionQueryService
    manifest_service: ExecutionManifestService
    action_generator: ExecutionActionGenerator
    start_service: ExecutionStartService
    runner: ExecutionRunner
    sandbox_enabled: bool


def create_execution_runtime(
    database: ContextDatabase,
    language_provider: LanguageProvider,
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

    approval_repository = (
        TaskApprovalRepository(
            database
        )
    )

    manifest_repository = (
        TaskExecutionManifestRepository(
            database
        )
    )

    manifest_service = (
        ExecutionManifestService(
            execution_repository=(
                execution_repository
            ),
            approval_repository=(
                approval_repository
            ),
            manifest_repository=(
                manifest_repository
            ),
        )
    )

    action_generator = (
        SplitExecutionActionGenerator(
            language_provider=(
                language_provider
            ),
            manifest_service=(
                manifest_service
            ),
            limits=limits,
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
                approval_repository
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

    start_service = ExecutionStartService(
        execution_repository=(
            execution_repository
        ),
        manifest_repository=(
            manifest_repository
        ),
        runner=runner,
    )

    return ExecutionRuntime(
        preparation_service=(
            preparation_service
        ),
        query_service=query_service,
        manifest_service=manifest_service,
        action_generator=action_generator,
        start_service=start_service,
        runner=runner,
        sandbox_enabled=(
            sandbox_executor is not None
        ),
    )