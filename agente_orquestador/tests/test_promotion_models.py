from dataclasses import FrozenInstanceError

import pytest

from app.execution.promotion_models import (
    PromotionChangeType,
    PromotionFileChange,
    PromotionPreview,
)


OLD_HASH = "a" * 64
NEW_HASH = "b" * 64
PREVIEW_HASH = "c" * 64


def create_change(
    relative_path: str = "suma.py",
    change_type: PromotionChangeType = (
        PromotionChangeType.ADDED
    ),
) -> PromotionFileChange:
    if (
        change_type
        == PromotionChangeType.ADDED
    ):
        previous_sha256 = None
        previous_size_bytes = None

    elif (
        change_type
        == PromotionChangeType.MODIFIED
    ):
        previous_sha256 = OLD_HASH
        previous_size_bytes = 10

    else:
        previous_sha256 = NEW_HASH
        previous_size_bytes = 20

    return PromotionFileChange(
        relative_path=relative_path,
        change_type=change_type,
        previous_sha256=previous_sha256,
        current_sha256=NEW_HASH,
        previous_size_bytes=(
            previous_size_bytes
        ),
        current_size_bytes=20,
        diff_text="diff",
    )


def test_creates_added_file_change() -> None:
    change = create_change()

    assert (
        change.change_type
        == PromotionChangeType.ADDED
    )
    assert change.previous_sha256 is None
    assert change.current_sha256 == NEW_HASH


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "",
        "   ",
        ".",
        "../fuera.py",
        "src/../../fuera.py",
        "/ruta/absoluta.py",
        r"C:\ruta\absoluta.py",
        r"src\modulo.py",
    ),
)
def test_rejects_unsafe_relative_path(
    unsafe_path: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="relative_path",
    ):
        create_change(
            relative_path=unsafe_path
        )


def test_rejects_invalid_sha256() -> None:
    with pytest.raises(
        ValueError,
        match="SHA-256",
    ):
        PromotionFileChange(
            relative_path="suma.py",
            change_type=(
                PromotionChangeType.ADDED
            ),
            previous_sha256=None,
            current_sha256="no-valido",
            previous_size_bytes=None,
            current_size_bytes=20,
            diff_text="diff",
        )


def test_rejects_modified_unchanged_hash(
) -> None:
    with pytest.raises(
        ValueError,
        match="cambiar su hash",
    ):
        PromotionFileChange(
            relative_path="suma.py",
            change_type=(
                PromotionChangeType.MODIFIED
            ),
            previous_sha256=NEW_HASH,
            current_sha256=NEW_HASH,
            previous_size_bytes=20,
            current_size_bytes=20,
            diff_text="",
        )


def test_counts_preview_changes() -> None:
    preview = PromotionPreview(
        workspace_path=(
            "C:/temporal/workspace"
        ),
        target_repository_root=(
            "C:/temporal/repository"
        ),
        changes=(
            create_change(
                relative_path="nuevo.py",
            ),
            create_change(
                relative_path="modificado.py",
                change_type=(
                    PromotionChangeType
                    .MODIFIED
                ),
            ),
            create_change(
                relative_path="igual.py",
                change_type=(
                    PromotionChangeType
                    .UNCHANGED
                ),
            ),
        ),
        preview_hash=PREVIEW_HASH,
    )

    assert preview.added_count == 1
    assert preview.modified_count == 1
    assert preview.unchanged_count == 1
    assert preview.changed_count == 2


def test_rejects_duplicate_paths() -> None:
    change = create_change()

    with pytest.raises(
        ValueError,
        match="duplicadas",
    ):
        PromotionPreview(
            workspace_path="workspace",
            target_repository_root=(
                "repository"
            ),
            changes=(
                change,
                change,
            ),
            preview_hash=PREVIEW_HASH,
        )


def test_models_are_immutable() -> None:
    change = create_change()

    with pytest.raises(
        FrozenInstanceError
    ):
        change.relative_path = "otro.py"