from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.context import (
    ContextDatabase,
    TaskApprovalRepository,
    TaskExecutionAttemptRepository,
    TaskExecutionManifestRepository,
    TaskExecutionPromotionRepository,
    TaskExecutionRepository,
    TaskExecutionStepRepository,
    TaskRepository,
)
from app.execution.action_generator import (
    ExecutionActionGenerator,
)
from app.execution.audited_promotion_finalization import (
    AuditedPromotionFinalizationService,
)
from app.execution.filesystem_executor import (
    SafeFilesystemExecutor,
)
from app.execution.git_promotion import (
    GitPromotionBranchService,
)
from app.execution.git_repository import (
    GitRepositoryInspector,
)
from app.execution.http_sandbox_backend import (
    HttpSandboxBackend,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.manifest_service import (
    ExecutionManifestService,
)
from app.execution.promotion_application import (
    PromotionApplicationService,
)
from app.execution.promotion_commit import (
    PromotionCommitService,
)
from app.execution.promotion_preparation import (
    PromotionPreparationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.promotion_validation import (
    PromotionValidationService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowService,
)
from app.execution.query import (
    ExecutionQueryService,
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
from app.execution.split_action_generator import (
    SplitExecutionActionGenerator,
)
from app.execution.start_service import (
    ExecutionStartService,
)
from app.execution.workspace import (
    WorkspacePolicy,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)
from app.providers.base import (
    LanguageProvider,
)
from app.execution.promotion_target import (
    PromotionTargetResolver,
)
from app.execution.promotion_query import (
    PromotionQueryService,
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
    promotion_preparation_service: (
        PromotionPreparationService
    )
    promotion_query_service: (
        PromotionQueryService
    )
    promotion_finalization_service: (
        AuditedPromotionFinalizationService
        | None
    )
    promotion_target_resolver: (
        PromotionTargetResolver | None
    )
    sandbox_enabled: bool


def create_execution_runtime(
    database: ContextDatabase,
    language_provider: LanguageProvider,
    execution_workspace_root: Path,
    protected_project_root: Path,
    sandbox_gateway_url: str | None,
    sandbox_gateway_token: str | None,
    sandbox_gateway_timeout_seconds: float,
    promotion_repository_root: (
        Path | None
    ) = None,
    promotion_allowed_projects: tuple[
        tuple[str, str],
        ...,
    ] = (),
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
    workspace_packager = WorkspacePackager()

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

    promotion_repository = (
        TaskExecutionPromotionRepository(
            database
        )
    )

    promotion_query_service = (
        PromotionQueryService(
            promotion_repository=(
                promotion_repository
            )
        )
    )

    task_repository = TaskRepository(
        database
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

    git_inspector = (
        GitRepositoryInspector()
    )

    promotion_target_resolver = None

    if promotion_repository_root is not None:
        promotion_target_resolver = (
            PromotionTargetResolver(
                execution_repository=(
                    execution_repository
                ),
                task_repository=(
                    task_repository
                ),
                git_inspector=git_inspector,
                repository_root=(
                    promotion_repository_root
                ),
                allowed_projects=dict(
                    promotion_allowed_projects
                ),
            )
        )

    elif promotion_allowed_projects:
        raise ValueError(
            "No pueden configurarse proyectos "
            "de promocion sin repositorio"
        )

    promotion_preview_service = (
        PromotionPreviewService(
            workspace_packager=(
                workspace_packager
            )
        )
    )

    promotion_preparation_service = (
        PromotionPreparationService(
            execution_repository=(
                execution_repository
            ),
            preview_service=(
                promotion_preview_service
            ),
            promotion_repository=(
                promotion_repository
            ),
        )
    )

    sandbox_executor = None
    promotion_finalization_service = None

    if (
        sandbox_gateway_url is not None
        and sandbox_gateway_token is not None
    ):
        backend = HttpSandboxBackend(
            gateway_url=sandbox_gateway_url,
            auth_token=sandbox_gateway_token,
            packager=workspace_packager,
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

        promotion_application_service = (
            PromotionApplicationService(
                preview_service=(
                    promotion_preview_service
                ),
                git_inspector=git_inspector,
            )
        )

        promotion_branch_service = (
            GitPromotionBranchService(
                git_inspector=git_inspector
            )
        )

        promotion_workflow_service = (
            PromotionWorkflowService(
                branch_service=(
                    promotion_branch_service
                ),
                application_service=(
                    promotion_application_service
                ),
            )
        )

        promotion_validation_service = (
            PromotionValidationService(
                workflow_service=(
                    promotion_workflow_service
                ),
                sandbox_backend=backend,
                limits=limits,
            )
        )

        promotion_commit_service = (
            PromotionCommitService(
                git_inspector=git_inspector
            )
        )

        promotion_finalization_service = (
            AuditedPromotionFinalizationService(
                promotion_repository=(
                    promotion_repository
                ),
                preview_service=(
                    promotion_preview_service
                ),
                workflow_service=(
                    promotion_workflow_service
                ),
                validation_service=(
                    promotion_validation_service
                ),
                commit_service=(
                    promotion_commit_service
                ),
            )
        )

    preparation_service = (
        ExecutionPreparationService(
            task_repository=task_repository,
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
        promotion_preparation_service=(
            promotion_preparation_service
        ),
        promotion_query_service=(
            promotion_query_service
        ),
        promotion_finalization_service=(
            promotion_finalization_service
        ),
        promotion_target_resolver=(
            promotion_target_resolver
        ),
        sandbox_enabled=(
            sandbox_executor is not None
        ),
    )