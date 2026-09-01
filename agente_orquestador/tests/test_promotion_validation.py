from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.promotion_validation import (
    PromotionValidationError,
    PromotionValidationService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowError,
)
from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)


class FakeSandboxBackend:
    def __init__(
        self,
        result: SandboxRunResult | None = None,
        error: RuntimeError | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.requests: list[
            SandboxRunRequest
        ] = []

    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        self.requests.append(request)

        if self._error is not None:
            raise self._error

        if self._result is None:
            raise RuntimeError(
                "No se configuro un resultado"
            )

        return self._result


def create_workflow_result(
    repository_root: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        branch=SimpleNamespace(
            repository_root=repository_root,
        ),
        application=object(),
    )


def create_successful_result(
) -> SandboxRunResult:
    return SandboxRunResult(
        exit_code=0,
        stdout_text="1 passed",
        stderr_text="",
        timed_out=False,
        duration_seconds=0.25,
    )


def test_validates_promotion_in_sandbox(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()
    sandbox_result = (
        create_successful_result()
    )
    backend = FakeSandboxBackend(
        result=sandbox_result
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(
            command_timeout_seconds=45.0,
            max_output_characters=12_000,
        ),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    result = service.validate(
        workflow_result=workflow_result,
        test_target="tests",
    )

    assert (
        result.workflow_result
        is workflow_result
    )
    assert (
        result.sandbox_result
        is sandbox_result
    )
    assert result.test_target == "tests"

    assert len(backend.requests) == 1

    request = backend.requests[0]

    assert (
        request.workspace_path
        == tmp_path.resolve()
    )
    assert request.test_target == "tests"
    assert request.timeout_seconds == 45.0
    assert (
        request.max_output_characters
        == 12_000
    )

    workflow_service.rollback.assert_not_called()


def test_rolls_back_after_failed_tests(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()

    sandbox_result = SandboxRunResult(
        exit_code=1,
        stdout_text="1 failed",
        stderr_text="AssertionError",
        timed_out=False,
        duration_seconds=0.30,
    )

    backend = FakeSandboxBackend(
        result=sandbox_result
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    with pytest.raises(
        PromotionValidationError,
        match="finalizaron con errores",
    ) as error_info:
        service.validate(
            workflow_result=workflow_result
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
    )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )


def test_rolls_back_after_timeout(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()

    sandbox_result = SandboxRunResult(
        exit_code=None,
        stdout_text="",
        stderr_text="",
        timed_out=True,
        duration_seconds=60.0,
    )

    backend = FakeSandboxBackend(
        result=sandbox_result
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    with pytest.raises(
        PromotionValidationError,
        match="agotaron el tiempo",
    ) as error_info:
        service.validate(
            workflow_result=workflow_result
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
    )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )


def test_rolls_back_after_sandbox_error(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()

    backend = FakeSandboxBackend(
        error=RuntimeError(
            "Gateway no disponible"
        )
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    with pytest.raises(
        PromotionValidationError,
        match="Gateway no disponible",
    ) as error_info:
        service.validate(
            workflow_result=workflow_result
        )

    assert (
        error_info.value.sandbox_result
        is None
    )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )


def test_reports_rollback_failure(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()

    workflow_service.rollback.side_effect = (
        PromotionWorkflowError(
            "No se pudo eliminar la rama"
        )
    )

    sandbox_result = SandboxRunResult(
        exit_code=1,
        stdout_text="1 failed",
        stderr_text="AssertionError",
        timed_out=False,
        duration_seconds=0.30,
    )

    backend = FakeSandboxBackend(
        result=sandbox_result
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    with pytest.raises(
        PromotionValidationError,
        match=(
            "no se pudo completar "
            "el rollback"
        ),
    ) as error_info:
        service.validate(
            workflow_result=workflow_result
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
    )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )


def test_rejects_unsafe_test_target(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()
    backend = FakeSandboxBackend(
        result=create_successful_result()
    )

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    with pytest.raises(
        PromotionValidationError,
        match="no es valida",
    ):
        service.validate(
            workflow_result=workflow_result,
            test_target="../tests",
        )

    assert backend.requests == []

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )

def test_validates_only_project_subdirectory(
    tmp_path: Path,
) -> None:
    workflow_service = Mock()
    backend = FakeSandboxBackend(
        result=create_successful_result()
    )

    project_directory = (
        tmp_path / "puntuacion_padel"
    )
    project_directory.mkdir()

    unrelated_directory = (
        tmp_path / "otro_proyecto"
    )
    unrelated_directory.mkdir()

    service = PromotionValidationService(
        workflow_service=workflow_service,
        sandbox_backend=backend,
        limits=ExecutionLimits(),
    )

    workflow_result = (
        create_workflow_result(tmp_path)
    )

    result = service.validate(
        workflow_result=workflow_result,
        test_target="tests",
        target_subdirectory=(
            "puntuacion_padel"
        ),
    )

    assert result.test_target == "tests"
    assert len(backend.requests) == 1

    request = backend.requests[0]

    assert (
        request.workspace_path
        == project_directory.resolve()
    )
    assert (
        request.workspace_path
        != tmp_path.resolve()
    )
    assert (
        request.workspace_path
        != unrelated_directory.resolve()
    )
    assert request.test_target == "tests"

    workflow_service.rollback.assert_not_called()