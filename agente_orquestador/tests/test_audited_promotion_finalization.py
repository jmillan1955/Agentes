from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.execution.audited_promotion_finalization import (
    AuditedPromotionFinalizationError,
    AuditedPromotionFinalizationService,
)
from app.execution.promotion_commit import (
    PromotionCommitError,
    PromotionCommitService,
)
from app.execution.promotion_preview import (
    PromotionPreviewService,
)
from app.execution.promotion_records import (
    PromotionStatus,
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


def create_service() -> tuple[
    AuditedPromotionFinalizationService,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
]:
    promotion_repository = Mock(
        spec=(
            TaskExecutionPromotionRepository
        )
    )
    preview_service = Mock(
        spec=PromotionPreviewService
    )
    workflow_service = Mock(
        spec=PromotionWorkflowService
    )
    validation_service = Mock(
        spec=PromotionValidationService
    )
    commit_service = Mock(
        spec=PromotionCommitService
    )

    service = (
        AuditedPromotionFinalizationService(
            promotion_repository=(
                promotion_repository
            ),
            preview_service=preview_service,
            workflow_service=workflow_service,
            validation_service=(
                validation_service
            ),
            commit_service=commit_service,
        )
    )

    return (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    )


def create_pending(
    tmp_path: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        execution_id=7,
        status=(
            PromotionStatus
            .PENDING_CONFIRMATION
        ),
        workspace_path=str(
            tmp_path / "workspace"
        ),
        repository_root=str(
            tmp_path / "repository"
        ),
        target_subdirectory=".",
        preview_hash="a" * 64,
        test_target="tests",
        confirmed_by_user_id=None,
        confirmation_message_id=None,
        confirmation_channel=None,
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
        stderr_text=(
            ""
            if exit_code == 0
            else "AssertionError"
        ),
        timed_out=timed_out,
        duration_seconds=0.25,
    )


def configure_successful_flow(
    tmp_path: Path,
    promotion_repository: Mock,
    preview_service: Mock,
    workflow_service: Mock,
    validation_service: Mock,
    commit_service: Mock,
):
    pending = create_pending(tmp_path)

    preview = SimpleNamespace(
        preview_hash=pending.preview_hash
    )

    confirmed = SimpleNamespace(
        id=pending.id,
        execution_id=pending.execution_id,
        preview_hash=pending.preview_hash,
        test_target=pending.test_target,
    )

    workflow_result = SimpleNamespace(
        branch=SimpleNamespace(
            promotion_branch=(
                "promotion/execution-7"
            ),
            base_commit="b" * 40,
        )
    )

    applied = SimpleNamespace(
        id=pending.id,
        test_target=pending.test_target,
        target_subdirectory=(
            pending.target_subdirectory
        ),
    )

    sandbox_result = (
        create_sandbox_result()
    )

    validation_result = SimpleNamespace(
        sandbox_result=sandbox_result
    )

    validated = SimpleNamespace(
        id=pending.id,
        execution_id=pending.execution_id,
    )

    commit_result = object()
    committed = object()

    promotion_repository.get_by_id.return_value = (
        pending
    )
    preview_service.create.return_value = (
        preview
    )
    promotion_repository.confirm.return_value = (
        confirmed
    )
    (
        workflow_service
        .apply_to_temporary_branch
        .return_value
    ) = workflow_result
    (
        promotion_repository
        .mark_applied
        .return_value
    ) = applied
    validation_service.validate.return_value = (
        validation_result
    )
    (
        promotion_repository
        .mark_validated
        .return_value
    ) = validated
    commit_service.commit.return_value = (
        commit_result
    )
    (
        promotion_repository
        .mark_committed
        .return_value
    ) = committed

    return SimpleNamespace(
        pending=pending,
        preview=preview,
        confirmed=confirmed,
        workflow_result=workflow_result,
        applied=applied,
        sandbox_result=sandbox_result,
        validation_result=(
            validation_result
        ),
        validated=validated,
        commit_result=commit_result,
        committed=committed,
    )


def test_finalizes_and_audits_promotion(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    flow = configure_successful_flow(
        tmp_path=tmp_path,
        promotion_repository=(
            promotion_repository
        ),
        preview_service=preview_service,
        workflow_service=workflow_service,
        validation_service=(
            validation_service
        ),
        commit_service=commit_service,
    )

    result = service.finalize(
        promotion_id=1,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
    )

    assert result is flow.committed

    preview_service.create.assert_called_once_with(
        workspace_path=Path(
            flow.pending.workspace_path
        ),
        target_repository_root=Path(
            flow.pending.repository_root
        ),
        target_subdirectory=(
            flow.pending
            .target_subdirectory
        ),
    )

    promotion_repository.confirm.assert_called_once_with(
        promotion_id=1,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
    )

    (
        workflow_service
        .apply_to_temporary_branch
        .assert_called_once_with(
            execution_id=7,
            preview=flow.preview,
            confirmed_preview_hash=(
                "a" * 64
            ),
        )
    )

    promotion_repository.mark_applied.assert_called_once_with(
        promotion_id=1,
        promotion_branch=(
            "promotion/execution-7"
        ),
        base_commit="b" * 40,
    )

    validation_service.validate.assert_called_once_with(
        workflow_result=flow.workflow_result,
        test_target="tests",
        target_subdirectory=".",
    )

    promotion_repository.mark_validated.assert_called_once_with(
        promotion_id=1,
        sandbox_result=flow.sandbox_result,
    )

    commit_service.commit.assert_called_once_with(
        execution_id=7,
        validation=flow.validation_result,
    )

    promotion_repository.mark_committed.assert_called_once_with(
        promotion_id=1,
        commit_result=flow.commit_result,
    )

    promotion_repository.mark_failed.assert_not_called()
    (
        promotion_repository
        .mark_rolled_back
        .assert_not_called()
    )


def test_rejects_stale_preview_and_audits_failure(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    pending = create_pending(tmp_path)

    promotion_repository.get_by_id.return_value = (
        pending
    )
    preview_service.create.return_value = (
        SimpleNamespace(
            preview_hash="f" * 64
        )
    )
    promotion_repository.mark_failed.return_value = (
        SimpleNamespace(id=1)
    )

    with pytest.raises(
        AuditedPromotionFinalizationError,
        match="cambiaron",
    ):
        service.finalize(
            promotion_id=1,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel=(
                "telegram"
            ),
        )

    promotion_repository.mark_failed.assert_called_once_with(
        promotion_id=1,
        error_message=(
            "El workspace o el repositorio "
            "cambiaron desde la vista previa"
        ),
        sandbox_result=None,
    )

    promotion_repository.confirm.assert_not_called()
    (
        workflow_service
        .apply_to_temporary_branch
        .assert_not_called()
    )
    validation_service.validate.assert_not_called()
    commit_service.commit.assert_not_called()


def test_audits_application_failure(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    pending = create_pending(tmp_path)

    promotion_repository.get_by_id.return_value = (
        pending
    )
    preview_service.create.return_value = (
        SimpleNamespace(
            preview_hash=pending.preview_hash
        )
    )
    promotion_repository.confirm.return_value = (
        SimpleNamespace(
            id=1,
            execution_id=7,
            preview_hash="a" * 64,
            test_target="tests",
        )
    )

    (
        workflow_service
        .apply_to_temporary_branch
        .side_effect
    ) = PromotionWorkflowError(
        "No se pudo crear la rama"
    )

    promotion_repository.mark_failed.return_value = (
        SimpleNamespace(id=1)
    )

    with pytest.raises(
        AuditedPromotionFinalizationError,
        match="No se pudo aplicar",
    ):
        service.finalize(
            promotion_id=1,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel=(
                "telegram"
            ),
        )

    promotion_repository.mark_failed.assert_called_once()
    (
        promotion_repository
        .mark_rolled_back
        .assert_called_once_with(
            promotion_id=1
        )
    )
    validation_service.validate.assert_not_called()
    commit_service.commit.assert_not_called()


def test_audits_validation_failure_and_rollback(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    flow = configure_successful_flow(
        tmp_path=tmp_path,
        promotion_repository=(
            promotion_repository
        ),
        preview_service=preview_service,
        workflow_service=workflow_service,
        validation_service=(
            validation_service
        ),
        commit_service=commit_service,
    )

    sandbox_result = create_sandbox_result(
        exit_code=1
    )

    validation_service.validate.side_effect = (
        PromotionValidationError(
            "Las pruebas fallaron",
            sandbox_result=sandbox_result,
        )
    )

    promotion_repository.mark_failed.return_value = (
        SimpleNamespace(id=1)
    )

    with pytest.raises(
        AuditedPromotionFinalizationError,
        match="no supero la validacion",
    ) as error_info:
        service.finalize(
            promotion_id=1,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel=(
                "telegram"
            ),
        )

    assert (
        error_info.value.sandbox_result
        is sandbox_result
    )

    promotion_repository.mark_failed.assert_called_once_with(
        promotion_id=1,
        error_message="Las pruebas fallaron",
        sandbox_result=sandbox_result,
    )

    (
        promotion_repository
        .mark_rolled_back
        .assert_called_once_with(
            promotion_id=1
        )
    )
    commit_service.commit.assert_not_called()


def test_rolls_back_and_audits_commit_failure(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    flow = configure_successful_flow(
        tmp_path=tmp_path,
        promotion_repository=(
            promotion_repository
        ),
        preview_service=preview_service,
        workflow_service=workflow_service,
        validation_service=(
            validation_service
        ),
        commit_service=commit_service,
    )

    commit_service.commit.side_effect = (
        PromotionCommitError(
            "Git rechazo el commit"
        )
    )
    promotion_repository.mark_failed.return_value = (
        SimpleNamespace(id=1)
    )

    with pytest.raises(
        AuditedPromotionFinalizationError,
        match="No se pudo crear el commit",
    ):
        service.finalize(
            promotion_id=1,
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel=(
                "telegram"
            ),
        )

    workflow_service.rollback.assert_called_once_with(
        flow.workflow_result
    )

    promotion_repository.mark_failed.assert_called_once_with(
        promotion_id=1,
        error_message="Git rechazo el commit",
        sandbox_result=flow.sandbox_result,
    )

    (
        promotion_repository
        .mark_rolled_back
        .assert_called_once_with(
            promotion_id=1
        )
    )


def test_repeats_committed_confirmation_idempotently(
    tmp_path: Path,
) -> None:
    (
        service,
        promotion_repository,
        preview_service,
        workflow_service,
        validation_service,
        commit_service,
    ) = create_service()

    committed = SimpleNamespace(
        id=1,
        status=PromotionStatus.COMMITTED,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
    )

    promotion_repository.get_by_id.return_value = (
        committed
    )

    result = service.finalize(
        promotion_id=1,
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
    )

    assert result is committed

    preview_service.create.assert_not_called()
    promotion_repository.confirm.assert_not_called()
    (
        workflow_service
        .apply_to_temporary_branch
        .assert_not_called()
    )
    validation_service.validate.assert_not_called()
    commit_service.commit.assert_not_called()