from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskApproval:
    id: int
    task_id: int
    plan_id: int
    plan_version: int
    authorized_user_id: str
    authorization_message_id: str
    channel: str
    created_at: str

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.task_id <= 0:
            raise ValueError(
                "task_id debe ser mayor que cero"
            )

        if self.plan_id <= 0:
            raise ValueError(
                "plan_id debe ser mayor que cero"
            )

        if self.plan_version <= 0:
            raise ValueError(
                "plan_version debe ser "
                "mayor que cero"
            )

        text_fields = (
            "authorized_user_id",
            "authorization_message_id",
            "channel",
            "created_at",
        )

        for field_name in text_fields:
            value = getattr(
                self,
                field_name,
            ).strip()

            if not value:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )