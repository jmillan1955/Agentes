import pytest

from app.execution.promotion_records import (
    PromotionStatus,
    TaskExecutionPromotion,
)
from app.execution.promotion_paths import (
    normalize_target_subdirectory,
)


def create_promotion(
    **overrides: object,
) -> TaskExecutionPromotion:
    values: dict[str, object] = {
        "id": 1,
        "execution_id": 7,
        "status": (
            PromotionStatus
            .PENDING_CONFIRMATION
        ),
        "workspace_path": (
            "/tmp/workspace"
        ),
        "repository_root": (
            "/tmp/repository"
        ),
        "preview_hash": "a" * 64,
        "changed_file_count": 2,
        "added_file_count": 1,
        "modified_file_count": 1,
        "requested_by_user_id": (
            "123456"
        ),
        "request_message_id": (
            "telegram:123"
        ),
        "channel": "telegram",
        "confirmed_by_user_id": None,
        "confirmation_message_id": None,
        "confirmation_channel": None,
        "test_target": "tests",
        "promotion_branch": None,
        "base_commit": None,
        "commit_hash": None,
        "sandbox_exit_code": None,
        "sandbox_timed_out": None,
        "sandbox_duration_seconds": None,
        "sandbox_stdout_text": None,
        "sandbox_stderr_text": None,
        "error_message": None,
        "created_at": (
            "2026-08-30T10:00:00.000Z"
        ),
        "confirmed_at": None,
        "finished_at": None,
    }

    values.update(overrides)

    return TaskExecutionPromotion(
        **values,
    )


def test_creates_pending_promotion() -> None:
    promotion = create_promotion()

    assert promotion.id == 1
    assert promotion.execution_id == 7
    assert (
        promotion.status
        == PromotionStatus
        .PENDING_CONFIRMATION
    )
    assert promotion.changed_file_count == 2
    assert promotion.preview_hash == "a" * 64


def test_normalizes_text_and_hashes() -> None:
    promotion = create_promotion(
        workspace_path=" /tmp/workspace ",
        repository_root=" /tmp/repository ",
        preview_hash="A" * 64,
        promotion_branch=(
            " promotion/execution-7 "
        ),
        base_commit="B" * 40,
    )

    assert (
        promotion.workspace_path
        == "/tmp/workspace"
    )
    assert (
        promotion.repository_root
        == "/tmp/repository"
    )
    assert promotion.preview_hash == "a" * 64
    assert (
        promotion.promotion_branch
        == "promotion/execution-7"
    )
    assert promotion.base_commit == "b" * 40


@pytest.mark.parametrize(
    "field_name",
    (
        "id",
        "execution_id",
    ),
)
def test_rejects_invalid_identifier(
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        create_promotion(
            **{
                field_name: 0,
            }
        )


@pytest.mark.parametrize(
    "preview_hash",
    (
        "",
        "a" * 63,
        "a" * 65,
        "z" * 64,
    ),
)
def test_rejects_invalid_preview_hash(
    preview_hash: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="preview_hash",
    ):
        create_promotion(
            preview_hash=preview_hash
        )


def test_rejects_inconsistent_counts() -> None:
    with pytest.raises(
        ValueError,
        match="changed_file_count",
    ):
        create_promotion(
            changed_file_count=3,
            added_file_count=1,
            modified_file_count=1,
        )


def test_rejects_empty_promotion() -> None:
    with pytest.raises(
        ValueError,
        match="al menos un cambio",
    ):
        create_promotion(
            changed_file_count=0,
            added_file_count=0,
            modified_file_count=0,
        )


def test_creates_committed_promotion() -> None:
    promotion = create_promotion(
        status=PromotionStatus.COMMITTED,
        promotion_branch=(
            "promotion/execution-7"
        ),
        base_commit="b" * 40,
        commit_hash="c" * 40,
        sandbox_exit_code=0,
        sandbox_timed_out=False,
        sandbox_duration_seconds=0.50,
        sandbox_stdout_text="1 passed",
        finished_at=(
            "2026-08-30T10:01:00.000Z"
        ),
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
        confirmed_at=(
            "2026-08-30T10:00:30.000Z"
        ),
    )

    assert (
        promotion.status
        == PromotionStatus.COMMITTED
    )
    assert promotion.commit_hash == "c" * 40
    assert promotion.sandbox_exit_code == 0
    assert (
        promotion.sandbox_timed_out
        is False
    )


def test_rejects_incomplete_committed_promotion(
) -> None:
    with pytest.raises(
        ValueError,
        match="validacion satisfactoria",
    ):
        create_promotion(
            status=PromotionStatus.COMMITTED,
            promotion_branch=(
                "promotion/execution-7"
            ),
            base_commit="b" * 40,
            commit_hash=None,
            sandbox_exit_code=0,
            sandbox_timed_out=False,
            finished_at=(
                "2026-08-30T10:01:00.000Z"
            ),
                        confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
            confirmed_at=(
                "2026-08-30T10:00:30.000Z"
            ),
        )


def test_creates_failed_promotion() -> None:
    promotion = create_promotion(
        status=PromotionStatus.FAILED,
        error_message=(
            "Las pruebas fallaron"
        ),
        finished_at=(
            "2026-08-30T10:01:00.000Z"
        ),
        confirmed_by_user_id="123456",
        confirmation_message_id=(
            "telegram:confirmacion:1"
        ),
        confirmation_channel="telegram",
        confirmed_at=(
            "2026-08-30T10:00:30.000Z"
        ),
    )

    assert (
        promotion.status
        == PromotionStatus.FAILED
    )
    assert (
        promotion.error_message
        == "Las pruebas fallaron"
    )


def test_rejects_failed_without_error() -> None:
    with pytest.raises(
        ValueError,
        match="conservar el error",
    ):
        create_promotion(
            status=PromotionStatus.FAILED,
            error_message=None,
            finished_at=(
                "2026-08-30T10:01:00.000Z"
            ),
            confirmed_by_user_id="123456",
            confirmation_message_id=(
                "telegram:confirmacion:1"
            ),
            confirmation_channel="telegram",
            confirmed_at=(
                "2026-08-30T10:00:30.000Z"
            ),
        )


def test_rejects_negative_duration() -> None:
    with pytest.raises(
        ValueError,
        match="duration",
    ):
        create_promotion(
            sandbox_duration_seconds=-0.1
        )

def test_rejects_partial_confirmation(
) -> None:
    with pytest.raises(
        ValueError,
        match="usuario, mensaje, canal y fecha",
    ):
        create_promotion(
            confirmed_by_user_id="123456",
            confirmation_message_id=None,
            confirmation_channel="telegram",
            confirmed_at=(
                "2026-08-30T10:00:30.000Z"
            ),
        )

def test_creates_unconfirmed_failed_promotion(
) -> None:
    promotion = create_promotion(
        status=PromotionStatus.FAILED,
        error_message=(
            "La vista previa ha caducado"
        ),
        finished_at=(
            "2026-08-31T08:00:00.000Z"
        ),
    )

    assert (
        promotion.status
        == PromotionStatus.FAILED
    )
    assert (
        promotion.confirmed_by_user_id
        is None
    )
    assert (
        promotion.error_message
        == "La vista previa ha caducado"
    )