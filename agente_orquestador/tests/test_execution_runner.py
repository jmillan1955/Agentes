from pathlib import Path

import pytest

from app.context import ContextDatabase
from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.filesystem_executor import (
    SafeFilesystemExecutor,
)
from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.models import (
    ExecutionAttemptStatus,
    ExecutionStatus,
    ExecutionStepStatus,
)
from app.execution.runner import (
    ExecutionRunError,
    ExecutionRunner,
)
from app.execution.workspace import (
    WorkspacePolicy,
)
from app.tasks import TaskStatus
from execution_support import (
    prepare_execution_context,
)
from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)
from app.execution.sandbox_executor import (
    SafeSandboxExecutor,
)
class FakeRunnerSandboxBackend:
    def __init__(
        self,
        result: SandboxRunResult,
    ) -> None:
        self.result = result
        self.requests: list[
            SandboxRunRequest
        ] = []

    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        self.requests.append(request)
        return self.result

def create_runner(
    context,
    root: Path,
    limits: ExecutionLimits | None = None,
    sandbox_backend=None,
) -> ExecutionRunner:
    effective_limits = (
        limits or ExecutionLimits()
    )

    return ExecutionRunner(
        execution_repository=(
            context.execution_repository
        ),
        attempt_repository=(
            context.attempt_repository
        ),
        step_repository=(
            context.step_repository
        ),
        filesystem_executor=(
            SafeFilesystemExecutor(
                workspace_policy=(
                    WorkspacePolicy(
                        allowed_root=root
                    )
                ),
                limits=effective_limits,
            )
        ),
        limits=effective_limits,
        sandbox_executor=(
            SafeSandboxExecutor(
                backend=sandbox_backend,
                limits=effective_limits,
            )
            if sandbox_backend is not None
            else None
        ),
    )


def test_runs_temporary_project_with_audit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"

    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=workspace,
        )
        runner = create_runner(
            context=context,
            root=root,
        )

        result = runner.run(
            execution_id=(
                context.execution.id
            ),
            actions=(
                ExecutionAction(
                    step_number=1,
                    name="Crear workspace",
                    action_type=(
                        ExecutionActionType
                        .CREATE_DIRECTORY
                    ),
                    relative_path=".",
                ),
                ExecutionAction(
                    step_number=2,
                    name="Crear src",
                    action_type=(
                        ExecutionActionType
                        .CREATE_DIRECTORY
                    ),
                    relative_path="src",
                ),
                ExecutionAction(
                    step_number=3,
                    name="Crear main",
                    action_type=(
                        ExecutionActionType
                        .WRITE_TEXT_FILE
                    ),
                    relative_path="src/main.py",
                    content="print('temporal')\n",
                ),
            ),
        )

        assert (
            result.execution.status
            == ExecutionStatus.COMPLETED
        )
        assert (
            result.attempt.status
            == ExecutionAttemptStatus.COMPLETED
        )
        assert len(result.steps) == 3
        assert all(
            step.status
            == ExecutionStepStatus.COMPLETED
            for step in result.steps
        )

        stored_task = (
            context.task_repository
            .get_by_id(
                result.execution.task_id
            )
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.COMPLETED
        )

        assert (
            workspace / "src" / "main.py"
        ).read_text(
            encoding="utf-8"
        ) == "print('temporal')\n"


def test_records_failed_action_and_attempt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"

    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=workspace,
        )
        runner = create_runner(
            context=context,
            root=root,
        )

        with pytest.raises(
            ExecutionRunError,
            match="directorio padre",
        ):
            runner.run(
                execution_id=(
                    context.execution.id
                ),
                actions=(
                    ExecutionAction(
                        step_number=1,
                        name="Crear workspace",
                        action_type=(
                            ExecutionActionType
                            .CREATE_DIRECTORY
                        ),
                        relative_path=".",
                    ),
                    ExecutionAction(
                        step_number=2,
                        name="Escribir sin carpeta",
                        action_type=(
                            ExecutionActionType
                            .WRITE_TEXT_FILE
                        ),
                        relative_path=(
                            "src/main.py"
                        ),
                        content="fallara\n",
                    ),
                ),
            )

        stored_execution = (
            context.execution_repository
            .get_by_id(
                context.execution.id
            )
        )

        assert stored_execution is not None
        assert (
            stored_execution.status
            == ExecutionStatus.FAILED
        )

        attempt = (
            context.attempt_repository
            .get_current(
                context.execution.id
            )
        )

        assert attempt is not None
        assert (
            attempt.status
            == ExecutionAttemptStatus.FAILED
        )

        steps = (
            context.step_repository
            .list_by_attempt(attempt.id)
        )

        assert len(steps) == 2
        assert (
            steps[0].status
            == ExecutionStepStatus.COMPLETED
        )
        assert (
            steps[1].status
            == ExecutionStepStatus.FAILED
        )

        stored_task = (
            context.task_repository
            .get_by_id(
                stored_execution.task_id
            )
        )

        assert stored_task is not None
        assert (
            stored_task.status
            == TaskStatus.IN_PROGRESS
        )
        assert not (
            workspace / "src" / "main.py"
        ).exists()


def test_rejects_too_many_actions_before_start(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"

    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=workspace,
        )
        limits = ExecutionLimits(
            max_actions=1
        )
        runner = create_runner(
            context=context,
            root=root,
            limits=limits,
        )

        actions = (
            ExecutionAction(
                step_number=1,
                name="Uno",
                action_type=(
                    ExecutionActionType
                    .CREATE_DIRECTORY
                ),
                relative_path=".",
            ),
            ExecutionAction(
                step_number=2,
                name="Dos",
                action_type=(
                    ExecutionActionType
                    .CREATE_DIRECTORY
                ),
                relative_path="src",
            ),
        )

        with pytest.raises(
            ExecutionRunError,
            match="numero maximo",
        ):
            runner.run(
                execution_id=(
                    context.execution.id
                ),
                actions=actions,
            )

        stored_execution = (
            context.execution_repository
            .get_by_id(
                context.execution.id
            )
        )

        assert stored_execution is not None
        assert (
            stored_execution.status
            == ExecutionStatus.PREPARED
        )
        assert workspace.exists() is False

def test_runs_pytest_through_sandbox_backend(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspaces"
    workspace = root / "temporal"

    backend = FakeRunnerSandboxBackend(
        SandboxRunResult(
            exit_code=0,
            stdout_text="1 passed",
            stderr_text="",
            timed_out=False,
            duration_seconds=0.2,
        )
    )

    with ContextDatabase(
        ":memory:"
    ) as database:
        context = prepare_execution_context(
            database=database,
            workspace_path=workspace,
        )

        runner = create_runner(
            context=context,
            root=root,
            sandbox_backend=backend,
        )

        result = runner.run(
            execution_id=(
                context.execution.id
            ),
            actions=(
                ExecutionAction(
                    step_number=1,
                    name="Crear workspace",
                    action_type=(
                        ExecutionActionType
                        .CREATE_DIRECTORY
                    ),
                    relative_path=".",
                ),
                ExecutionAction(
                    step_number=2,
                    name="Crear tests",
                    action_type=(
                        ExecutionActionType
                        .CREATE_DIRECTORY
                    ),
                    relative_path="tests",
                ),
                ExecutionAction(
                    step_number=3,
                    name="Crear prueba",
                    action_type=(
                        ExecutionActionType
                        .WRITE_TEXT_FILE
                    ),
                    relative_path=(
                        "tests/test_temporal.py"
                    ),
                    content=(
                        "def test_temporal():\n"
                        "    assert True\n"
                    ),
                ),
                ExecutionAction(
                    step_number=4,
                    name="Ejecutar pruebas",
                    action_type=(
                        ExecutionActionType
                        .RUN_PYTEST
                    ),
                    relative_path="tests",
                ),
            ),
        )

        assert (
            result.execution.status
            == ExecutionStatus.COMPLETED
        )
        assert len(result.steps) == 4
        assert (
            result.steps[-1].status
            == ExecutionStepStatus.COMPLETED
        )
        assert (
            result.steps[-1].stdout_text
            == "1 passed"
        )

        assert len(backend.requests) == 1
        assert (
            backend.requests[0].test_target
            == "tests"
        )
        assert (
            backend.requests[0].workspace_path
            == workspace.resolve()
        )