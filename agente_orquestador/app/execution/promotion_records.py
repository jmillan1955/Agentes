from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromotionStatus(str, Enum):
    PENDING_CONFIRMATION = (
        "pending_confirmation"
    )
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    VALIDATED = "validated"
    COMMITTED = "committed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class TaskExecutionPromotion:
    id: int
    execution_id: int
    status: PromotionStatus
    workspace_path: str
    repository_root: str
    preview_hash: str
    changed_file_count: int
    added_file_count: int
    modified_file_count: int
    requested_by_user_id: str
    request_message_id: str
    channel: str
    confirmed_by_user_id: str | None
    confirmation_message_id: str | None
    confirmation_channel: str | None
    test_target: str
    promotion_branch: str | None
    base_commit: str | None
    commit_hash: str | None
    sandbox_exit_code: int | None
    sandbox_timed_out: bool | None
    sandbox_duration_seconds: float | None
    sandbox_stdout_text: str | None
    sandbox_stderr_text: str | None
    error_message: str | None
    created_at: str
    confirmed_at: str | None
    finished_at: str | None

    def __post_init__(self) -> None:
        identifiers = {
            "id": self.id,
            "execution_id": (
                self.execution_id
            ),
        }

        for field_name, value in (
            identifiers.items()
        ):
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero"
                )

        required_text_fields = {
            "workspace_path": (
                self.workspace_path
            ),
            "repository_root": (
                self.repository_root
            ),
            "preview_hash": (
                self.preview_hash
            ),
            "requested_by_user_id": (
                self.requested_by_user_id
            ),
            "request_message_id": (
                self.request_message_id
            ),
            "channel": self.channel,
            "test_target": self.test_target,
            "created_at": self.created_at,
        }

        normalized_required: dict[
            str,
            str,
        ] = {}

        for field_name, value in (
            required_text_fields.items()
        ):
            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    f"{field_name} no puede "
                    "estar vacio"
                )

            normalized_required[
                field_name
            ] = normalized

        preview_hash = normalized_required[
            "preview_hash"
        ].lower()

        if (
            len(preview_hash) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in preview_hash
            )
        ):
            raise ValueError(
                "preview_hash debe ser un hash "
                "SHA-256 valido"
            )

        counts = {
            "changed_file_count": (
                self.changed_file_count
            ),
            "added_file_count": (
                self.added_file_count
            ),
            "modified_file_count": (
                self.modified_file_count
            ),
        }

        for field_name, value in (
            counts.items()
        ):
            if value < 0:
                raise ValueError(
                    f"{field_name} no puede "
                    "ser negativo"
                )

        if (
            self.changed_file_count
            != self.added_file_count
            + self.modified_file_count
        ):
            raise ValueError(
                "changed_file_count debe "
                "coincidir con los archivos "
                "anadidos y modificados"
            )

        if self.changed_file_count == 0:
            raise ValueError(
                "La promocion debe contener "
                "al menos un cambio"
            )

        optional_text_fields = (
            "promotion_branch",
            "base_commit",
            "commit_hash",
            "sandbox_stdout_text",
            "sandbox_stderr_text",
            "error_message",
            "confirmed_at",
            "finished_at",
            "confirmed_by_user_id",
            "confirmation_message_id",
            "confirmation_channel",
        )

        for field_name in optional_text_fields:
            value = getattr(
                self,
                field_name,
            )

            if value is None:
                continue

            normalized = value.strip()

            if not normalized:
                normalized = None

            object.__setattr__(
                self,
                field_name,
                normalized,
            )
        confirmation_fields = (
            self.confirmed_by_user_id,
            self.confirmation_message_id,
            self.confirmation_channel,
            self.confirmed_at,
        )

        has_confirmation = any(
            value is not None
            for value in confirmation_fields
        )

        has_complete_confirmation = all(
            value is not None
            for value in confirmation_fields
        )

        if (
            has_confirmation
            and not has_complete_confirmation
        ):
            raise ValueError(
                "La confirmacion debe conservar "
                "usuario, mensaje, canal y fecha"
            )

        if (
            self.status
            not in {
                PromotionStatus
                .PENDING_CONFIRMATION,
                PromotionStatus.FAILED,
            }
            and not has_complete_confirmation
        ):            raise ValueError(
                "La promocion debe conservar "
                "la confirmacion autorizada"
            )

        for field_name in (
            "base_commit",
            "commit_hash",
        ):
            value = getattr(
                self,
                field_name,
            )

            if (
                value is not None
                and (
                    len(value) != 40
                    or any(
                        character
                        not in (
                            "0123456789abcdef"
                        )
                        for character
                        in value.lower()
                    )
                )
            ):
                raise ValueError(
                    f"{field_name} debe ser un "
                    "hash Git valido"
                )

            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    value.lower(),
                )

        if (
            self.sandbox_duration_seconds
            is not None
            and self.sandbox_duration_seconds < 0
        ):
            raise ValueError(
                "sandbox_duration_seconds no "
                "puede ser negativo"
            )

        if (
            self.sandbox_timed_out is not None
            and not isinstance(
                self.sandbox_timed_out,
                bool,
            )
        ):
            raise ValueError(
                "sandbox_timed_out debe ser "
                "booleano o null"
            )

        if (
            self.status
            == PromotionStatus.COMMITTED
            and (
                self.promotion_branch is None
                or self.base_commit is None
                or self.commit_hash is None
                or self.sandbox_exit_code != 0
                or self.sandbox_timed_out
                is not False
                or self.finished_at is None
            )
        ):
            raise ValueError(
                "Una promocion confirmada en "
                "Git debe contener rama, commits "
                "y validacion satisfactoria"
            )

        if (
            self.status
            == PromotionStatus.FAILED
            and (
                self.error_message is None
                or self.finished_at is None
            )
        ):
            raise ValueError(
                "Una promocion fallida debe "
                "conservar el error y la fecha "
                "de finalizacion"
            )

        for field_name, normalized in (
            normalized_required.items()
        ):
            object.__setattr__(
                self,
                field_name,
                normalized,
            )

        object.__setattr__(
            self,
            "preview_hash",
            preview_hash,
        )