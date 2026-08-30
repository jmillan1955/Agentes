from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.promotion_commit import (
    PromotionCommitError,
    PromotionCommitService,
)
from app.execution.promotion_finalization import (
    PromotionFinalizationError,
    PromotionFinalizationService,
)
from app.execution.promotion_validation import (
    PromotionValidationError,
    PromotionValidationService,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowError,
    PromotionWorkflowService,
)
from app.execution.sandbox import (
    SandboxRunResult,
)


def create_services() -> tuple[
    PromotionFinalizationService,
    Mock,
    Mock,
    Mock,
]:
    workflow_service = Mock(
        spec=PromotionWorkflowService
    )
    validation_service = Mock(
        spec=PromotionValidationService
    )
    commit_service = Mock(
        spec=PromotionCommitService
    )

    service = PromotionFinalizationService(
        workflow_service=workflow_service,
        validation_service=(
            validation_service
        ),
        commit_service=commit_service,
    )

    return (
        service,
        workflow_service,
        validation_service,
        commit_service,
    )


def create_preview() -> SimpleNamespace:
    return SimpleNamespace(
        preview_hash="a" * 64,
    )


def create_sandbox_result(
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> SandboxRunResult:
    return SandboxRunResult(
        exit_code=exit_code,
        stdout_text=(
            "1 passed"
            if exit_code == 0
            else "1 failed"
        ),
        stderr_text="",
        timed_out=timed_out,
        duration_seconds=0.25,
    )


def test_finalizes_validated_promotion(
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    preview = create_preview()
    workflow_result = object()

    validation_result = SimpleNamespace(
        sandbox_result=(
            create_sandbox_result()
        )
    )
    commit_result = object()

    (
        workflow_service
        .apply_to_temporary_branch
        .return_value
    ) = workflow_result

    validation_service.validate.return_value = (
        validation_result
    )
    commit_service.commit.return_value = (
        commit_result
    )

    result = service.finalize(
        execution_id=7,
        preview=preview,
        confirmed_preview_hash=(
            preview.preview_hash
        ),
        test_target="tests",
    )

    assert result.workflow is workflow_result
    assert (
        result.validation
        is validation_result
    )
    assert result.commit is commit_result

    (
        workflow_service
        .apply_to_temporary_branch
        .assert_called_once_with(
            execution_id=7,
            preview=preview,
            confirmed_preview_hash=(
                preview.preview_hash
            ),
        )
    )

    validation_service.validate.assert_called_once_with(
        workflow_result=workflow_result,
        test_target="tests",
    )

    commit_service.commit.assert_called_once_with(
        execution_id=7,
        validation=validation_result,
    )

    workflow_service.rollback.assert_not_called()


@pytest.mark.parametrize(
    "execution_id",
    (
        0,
        -1,
    ),
)
def test_rejects_invalid_execution_id(
    execution_id: int,
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    with pytest.raises(
        PromotionFinalizationError,
        match="execution_id",
    ):
        service.finalize(
            execution_id=execution_id,
            preview=create_preview(),
            confirmed_preview_hash="a" * 64,
        )

    (
        workflow_service
        .apply_to_temporary_branch
        .assert_not_called()
    )
    validation_service.validate.assert_not_called()
    commit_service.commit.assert_not_called()


def test_reports_application_failure(
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    (
        workflow_service
        .apply_to_temporary_branch
        .side_effect
    ) = PromotionWorkflowError(
        "El hash no coincide"
    )

    with pytest.raises(
        PromotionFinalizationError,
        match="No se pudo aplicar",
    ):
        service.finalize(
            execution_id=7,
            preview=create_preview(),
            confirmed_preview_hash="0" * 64,
        )

    validation_service.validate.assert_not_called()
    commit_service.commit.assert_not_called()
    workflow_service.rollback.assert_not_called()


def test_preserves_failed_sandbox_result(
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    workflow_result = object()
    sandbox_result = create_sandbox_result(
        exit_code=1
    )

    (
        workflow_service
        .apply_to_temporary_branch
        .return_value
    ) = workflow_result

    validation_service.validate.side_effect = (
        PromotionValidationError(
            "Las pruebas fallaron",
            sandbox_result=sandbox_result,
        )
    )

    with pytest.raises(
        PromotionFinalizationError,
        match="no supero la validacion",
    ) as error_info:
        service.finalize(
            execution_id=7,
            preview=create_preview(),
            confirmed_preview_hash="a" * 64,
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
    )

    commit_service.commit.assert_not_called()

    # PromotionValidationService ya realiza
    # el rollback cuando falla el sandbox.
    workflow_service.rollback.assert_not_called()


def test_rolls_back_after_commit_failure(
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    workflow_result = object()
    validation_result = SimpleNamespace(
        sandbox_result=(
            create_sandbox_result()
        )
    )

    (
        workflow_service
        .apply_to_temporary_branch
        .return_value
    ) = workflow_result

    validation_service.validate.return_value = (
        validation_result
    )

    commit_service.commit.side_effect = (
        PromotionCommitError(
            "Git rechazo el commit"
        )
    )

    with pytest.raises(
        PromotionFinalizationError,
        match="No se pudo crear el commit",
    ):
        service.finalize(
            execution_id=7,
            preview=create_preview(),
            confirmed_preview_hash="a" * 64,
        )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )


def test_reports_commit_and_rollback_failure(
) -> None:
    (
        service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_services()

    workflow_result = object()
    validation_result = SimpleNamespace(
        sandbox_result=(
            create_sandbox_result()
        )
    )

    (
        workflow_service
        .apply_to_temporary_branch
        .return_value
    ) = workflow_result

    validation_service.validate.return_value = (
        validation_result
    )

    commit_service.commit.side_effect = (
        PromotionCommitError(
            "Git rechazo el commit"
        )
    )

    workflow_service.rollback.side_effect = (
        PromotionWorkflowError(
            "No se pudo eliminar la rama"
        )
    )

    with pytest.raises(
        PromotionFinalizationError,
        match=(
            "tampoco se pudo completar "
            "el rollback"
        ),
    ):
        service.finalize(
            execution_id=7,
            preview=create_preview(),
            confirmed_preview_hash="a" * 64,
        )

    workflow_service.rollback.assert_called_once_with(
        workflow_result
    )