import pytest

from app.execution.manifest_models import (
    ExecutionManifest,
    ExecutionManifestAction,
    ExecutionManifestStatus,
)


def test_creates_execution_manifest() -> None:
    manifest = ExecutionManifest(
        id=1,
        execution_id=5,
        version=1,
        status=(
            ExecutionManifestStatus
            .PENDING_CONFIRMATION
        ),
        manifest_hash="a" * 64,
        action_count=3,
        destructive_action_count=1,
        created_at="2026-08-27T16:00:00Z",
        confirmed_at=None,
        confirmed_by_user_id=None,
        confirmation_message_id=None,
        confirmation_channel=None,
    )

    assert manifest.execution_id == 5
    assert manifest.version == 1
    assert manifest.action_count == 3
    assert manifest.is_confirmed is False
    assert manifest.requires_extra_confirmation


def test_creates_manifest_action() -> None:
    action = ExecutionManifestAction(
        id=2,
        manifest_id=1,
        step_number=1,
        name="Crear archivo",
        action_type="write_text_file",
        relative_path="app/main.py",
        content_text="print('hola')\n",
        content_sha256="b" * 64,
        destructive=True,
        created_at="2026-08-27T16:00:00Z",
    )

    assert action.step_number == 1
    assert action.destructive is True


def test_reports_confirmed_manifest() -> None:
    manifest = ExecutionManifest(
        id=1,
        execution_id=5,
        version=1,
        status=(
            ExecutionManifestStatus.CONFIRMED
        ),
        manifest_hash="a" * 64,
        action_count=1,
        destructive_action_count=0,
        created_at="2026-08-27T16:00:00Z",
        confirmed_at="2026-08-27T16:05:00Z",
        confirmed_by_user_id="123456",
        confirmation_message_id="mensaje-1",
        confirmation_channel="telegram",
    )

    assert manifest.is_confirmed is True
    assert (
        manifest.requires_extra_confirmation
        is False
    )


@pytest.mark.parametrize(
    "manifest_hash",
    (
        "",
        "abc",
        "z" * 64,
    ),
)
def test_rejects_invalid_manifest_hash(
    manifest_hash: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="manifest_hash",
    ):
        ExecutionManifest(
            id=1,
            execution_id=5,
            version=1,
            status=(
                ExecutionManifestStatus.DRAFT
            ),
            manifest_hash=manifest_hash,
            action_count=1,
            destructive_action_count=0,
            created_at=(
                "2026-08-27T16:00:00Z"
            ),
            confirmed_at=None,
            confirmed_by_user_id=None,
            confirmation_message_id=None,
            confirmation_channel=None,
        )