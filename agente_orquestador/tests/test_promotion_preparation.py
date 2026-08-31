from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.context.task_execution_promotion_repository import (
    TaskExecutionPromotionRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.execution.models import (
    ExecutionStatus,
)
from app.execution.promotion_preparation import (
    PromotionPreparationError,
    PromotionPreparationService,
)
from app.execution.promotion_preview import (
    PromotionPreviewError,
    PromotionPreviewService,
)


def create_service() -> tuple[
    PromotionPreparationService,
    Mock,
    Mock,
    Mock,
]:
    execution_repository = Mock(
        spec=TaskExecutionRepository
    )
    preview_service = Mock(
        spec=PromotionPreviewService
    )
    promotion_repository = Mock(
        spec=(
            TaskExecutionPromotionRepository
        )
    )

    service = PromotionPreparationService(
        execution_repository=(
            execution_repository
        ),
        preview_service=preview_service,
        promotion_repository=(
            promotion_repository
        ),
    )

    return (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    )


def create_execution(
    workspace_path: Path,
    status: ExecutionStatus = (
        ExecutionStatus.COMPLETED
    ),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        workspace_path=str(workspace_path),
        status=status,
    )


def test_prepares_promotion_preview(
    tmp_path: Path,
) -> None:
    (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    ) = create_service()

    workspace = tmp_path / "workspace"
    repository_root = (
        tmp_path / "repository"
    )

    execution = create_execution(
        workspace
    )
    preview = object()
    promotion = object()

    (
        execution_repository
        .get_by_id
        .return_value
    ) = execution
    preview_service.create.return_value = (
        preview
    )
    (
        promotion_repository
        .create_pending
        .return_value
    ) = promotion

    result = service.prepare(
        execution_id=7,
        target_repository_root=(
            repository_root
        ),
        requested_by_user_id="123456",
        request_message_id=(
            "telegram:promocion:1"
        ),
        channel="telegram",
        target_subdirectory=(
            "puntuacion_padel"
        ),
        test_target="tests",
    )

    assert result.preview is preview
    assert result.promotion is promotion

    execution_repository.get_by_id.assert_called_once_with(
        7
    )

    preview_service.create.assert_called_once_with(
        workspace_path=workspace,
        target_repository_root=(
            repository_root
        ),
        target_subdirectory=(
            "puntuacion_padel"
        ),
    )

    (
        promotion_repository
        .create_pending
        .assert_called_once_with(
            execution_id=7,
            preview=preview,
            requested_by_user_id=(
                "123456"
            ),
            request_message_id=(
                "telegram:promocion:1"
            ),
            channel="telegram",
            test_target="tests",
        )
    )


def test_rejects_missing_execution(
    tmp_path: Path,
) -> None:
    (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    ) = create_service()

    (
        execution_repository
        .get_by_id
        .return_value
    ) = None

    with pytest.raises(
        PromotionPreparationError,
        match="No existe",
    ):
        service.prepare(
            execution_id=7,
            target_repository_root=(
                tmp_path / "repository"
            ),
            requested_by_user_id="123456",
            request_message_id="mensaje",
            channel="telegram",
        )

    preview_service.create.assert_not_called()

    (
        promotion_repository
        .create_pending
        .assert_not_called()
    )


def test_rejects_non_completed_execution(
    tmp_path: Path,
) -> None:
    (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    ) = create_service()

    (
        execution_repository
        .get_by_id
        .return_value
    ) = create_execution(
        workspace_path=(
            tmp_path / "workspace"
        ),
        status=ExecutionStatus.FAILED,
    )

    with pytest.raises(
        PromotionPreparationError,
        match="ejecucion completada",
    ):
        service.prepare(
            execution_id=7,
            target_repository_root=(
                tmp_path / "repository"
            ),
            requested_by_user_id="123456",
            request_message_id="mensaje",
            channel="telegram",
        )

    preview_service.create.assert_not_called()

    (
        promotion_repository
        .create_pending
        .assert_not_called()
    )


def test_reports_preview_error(
    tmp_path: Path,
) -> None:
    (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    ) = create_service()

    (
        execution_repository
        .get_by_id
        .return_value
    ) = create_execution(
        tmp_path / "workspace"
    )

    preview_service.create.side_effect = (
        PromotionPreviewError(
            "El repositorio no es valido"
        )
    )

    with pytest.raises(
        PromotionPreparationError,
        match="repositorio no es valido",
    ):
        service.prepare(
            execution_id=7,
            target_repository_root=(
                tmp_path / "repository"
            ),
            requested_by_user_id="123456",
            request_message_id="mensaje",
            channel="telegram",
        )

    (
        promotion_repository
        .create_pending
        .assert_not_called()
    )


def test_reports_persistence_error(
    tmp_path: Path,
) -> None:
    (
        service,
        execution_repository,
        preview_service,
        promotion_repository,
    ) = create_service()

    (
        execution_repository
        .get_by_id
        .return_value
    ) = create_execution(
        tmp_path / "workspace"
    )

    preview_service.create.return_value = (
        object()
    )

    (
        promotion_repository
        .create_pending
        .side_effect
    ) = ValueError(
        "La vista previa ya fue registrada"
    )

    with pytest.raises(
        PromotionPreparationError,
        match="ya fue registrada",
    ):
        service.prepare(
            execution_id=7,
            target_repository_root=(
                tmp_path / "repository"
            ),
            requested_by_user_id="123456",
            request_message_id="mensaje",
            channel="telegram",
        )