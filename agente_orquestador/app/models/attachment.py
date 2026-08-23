from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.message_types import ContentType


@dataclass(frozen=True, slots=True)
class Attachment:
    attachment_id: str
    content_type: ContentType
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None
    local_path: Path | None = None
    remote_id: str | None = None

    def __post_init__(self) -> None:
        if not self.attachment_id.strip():
            raise ValueError(
                "attachment_id no puede estar vacío"
            )

        if not self.filename.strip():
            raise ValueError(
                "filename no puede estar vacío"
            )

        if (
            self.size_bytes is not None
            and self.size_bytes < 0
        ):
            raise ValueError(
                "size_bytes no puede ser negativo"
            )