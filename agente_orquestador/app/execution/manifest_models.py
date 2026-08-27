from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from string import hexdigits


class ExecutionManifestStatus(
    str,
    Enum,
):
    DRAFT = "draft"
    PENDING_CONFIRMATION = (
        "pending_confirmation"
    )
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ExecutionManifest:
    id: int
    execution_id: int
    version: int
    status: ExecutionManifestStatus
    manifest_hash: str
    action_count: int
    destructive_action_count: int
    created_at: str
    confirmed_at: str | None
    confirmed_by_user_id: str | None
    confirmation_message_id: str | None
    confirmation_channel: str | None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        if self.version <= 0:
            raise ValueError(
                "version debe ser "
                "mayor que cero"
            )

        try:
            normalized_status = (
                ExecutionManifestStatus(
                    self.status
                )
            )

        except ValueError as error:
            raise ValueError(
                "status no es valido"
            ) from error

        normalized_hash = (
            self.manifest_hash
            .strip()
            .lower()
        )

        if (
            len(normalized_hash) != 64
            or any(
                character not in hexdigits
                for character
                in normalized_hash
            )
        ):
            raise ValueError(
                "manifest_hash no es valido"
            )

        if self.action_count <= 0:
            raise ValueError(
                "action_count debe ser "
                "mayor que cero"
            )

        if (
            self.destructive_action_count
            < 0
            or self.destructive_action_count
            > self.action_count
        ):
            raise ValueError(
                "destructive_action_count "
                "no es valido"
            )

        if (
            normalized_status
            == ExecutionManifestStatus
            .CONFIRMED
            and (
                not self.confirmed_at
                or not self.confirmed_by_user_id
                or not self
                .confirmation_message_id
                or not self
                .confirmation_channel
            )
        ):
            raise ValueError(
                "Un manifiesto confirmado "
                "requiere los datos de "
                "confirmacion"
            )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )
        object.__setattr__(
            self,
            "manifest_hash",
            normalized_hash,
        )

    @property
    def is_confirmed(self) -> bool:
        return (
            self.status
            == ExecutionManifestStatus.CONFIRMED
        )

    @property
    def requires_extra_confirmation(
        self,
    ) -> bool:
        return (
            self.destructive_action_count
            > 0
        )


@dataclass(frozen=True, slots=True)
class ExecutionManifestAction:
    id: int
    manifest_id: int
    step_number: int
    name: str
    action_type: str
    relative_path: str
    content_text: str | None
    content_sha256: str | None
    destructive: bool
    created_at: str

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.manifest_id <= 0:
            raise ValueError(
                "manifest_id debe ser "
                "mayor que cero"
            )

        if self.step_number <= 0:
            raise ValueError(
                "step_number debe ser "
                "mayor que cero"
            )

        normalized_name = self.name.strip()
        normalized_path = (
            self.relative_path.strip()
        )

        if not normalized_name:
            raise ValueError(
                "name no puede estar vacio"
            )

        if not normalized_path:
            raise ValueError(
                "relative_path no puede "
                "estar vacio"
            )

        if self.action_type not in {
            "create_directory",
            "write_text_file",
            "run_pytest",
        }:
            raise ValueError(
                "action_type no es valido"
            )

        if self.content_sha256 is not None:
            normalized_content_hash = (
                self.content_sha256
                .strip()
                .lower()
            )

            if (
                len(
                    normalized_content_hash
                ) != 64
                or any(
                    character not in hexdigits
                    for character
                    in normalized_content_hash
                )
            ):
                raise ValueError(
                    "content_sha256 no es "
                    "valido"
                )

            object.__setattr__(
                self,
                "content_sha256",
                normalized_content_hash,
            )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )
        object.__setattr__(
            self,
            "relative_path",
            normalized_path,
        )