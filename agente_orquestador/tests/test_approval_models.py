from dataclasses import replace

import pytest

from app.approvals import TaskApproval


def create_approval() -> TaskApproval:
    return TaskApproval(
        id=1,
        task_id=2,
        plan_id=3,
        plan_version=4,
        authorized_user_id="8288969559",
        authorization_message_id=(
            "telegram:8288969559:120"
        ),
        channel="telegram",
        created_at=(
            "2026-08-26T06:00:00.000Z"
        ),
    )


def test_creates_task_approval() -> None:
    approval = create_approval()

    assert approval.id == 1
    assert approval.task_id == 2
    assert approval.plan_id == 3
    assert approval.plan_version == 4
    assert (
        approval.authorized_user_id
        == "8288969559"
    )
    assert (
        approval.authorization_message_id
        == "telegram:8288969559:120"
    )
    assert approval.channel == "telegram"


def test_normalizes_task_approval_texts() -> None:
    approval = TaskApproval(
        id=1,
        task_id=2,
        plan_id=3,
        plan_version=4,
        authorized_user_id=" 8288969559 ",
        authorization_message_id=(
            " telegram:8288969559:120 "
        ),
        channel=" telegram ",
        created_at=(
            " 2026-08-26T06:00:00.000Z "
        ),
    )

    assert (
        approval.authorized_user_id
        == "8288969559"
    )
    assert (
        approval.authorization_message_id
        == "telegram:8288969559:120"
    )
    assert approval.channel == "telegram"
    assert (
        approval.created_at
        == "2026-08-26T06:00:00.000Z"
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("id", 0),
        ("task_id", 0),
        ("plan_id", 0),
        ("plan_version", 0),
    ),
)
def test_rejects_invalid_numeric_fields(
    field_name: str,
    field_value: int,
) -> None:
    approval = create_approval()

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} debe ser"
        ),
    ):
        replace(
            approval,
            **{
                field_name: field_value,
            },
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "authorized_user_id",
        "authorization_message_id",
        "channel",
        "created_at",
    ),
)
def test_rejects_empty_text_fields(
    field_name: str,
) -> None:
    approval = create_approval()

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} no puede"
        ),
    ):
        replace(
            approval,
            **{
                field_name: "   ",
            },
        )