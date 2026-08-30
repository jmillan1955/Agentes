from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import (
    PurePosixPath,
    PureWindowsPath,
)


_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class PromotionChangeType(
    str,
    Enum,
):
    ADDED = "added"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class PromotionFileChange:
    relative_path: str
    change_type: PromotionChangeType
    previous_sha256: str | None
    current_sha256: str
    previous_size_bytes: int | None
    current_size_bytes: int
    diff_text: str

    def __post_init__(self) -> None:
        relative_path = (
            self.relative_path.strip()
        )

        if not relative_path:
            raise ValueError(
                "relative_path no puede estar "
                "vacio"
            )

        posix_path = PurePosixPath(
            relative_path
        )
        windows_path = PureWindowsPath(
            relative_path
        )

        if (
            "\\" in relative_path
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(
                "relative_path no es segura"
            )

        if relative_path == ".":
            raise ValueError(
                "relative_path debe identificar "
                "un archivo"
            )

        if not isinstance(
            self.change_type,
            PromotionChangeType,
        ):
            raise ValueError(
                "change_type no es valido"
            )

        self._validate_sha256(
            value=self.current_sha256,
            field_name="current_sha256",
        )

        if self.current_size_bytes < 0:
            raise ValueError(
                "current_size_bytes no puede "
                "ser negativo"
            )

        if not isinstance(
            self.diff_text,
            str,
        ):
            raise ValueError(
                "diff_text debe ser texto"
            )

        if (
            self.change_type
            == PromotionChangeType.ADDED
        ):
            if (
                self.previous_sha256 is not None
                or self.previous_size_bytes
                is not None
            ):
                raise ValueError(
                    "Un archivo nuevo no puede "
                    "tener estado anterior"
                )

        else:
            if self.previous_sha256 is None:
                raise ValueError(
                    "El cambio debe conservar "
                    "previous_sha256"
                )

            self._validate_sha256(
                value=self.previous_sha256,
                field_name=(
                    "previous_sha256"
                ),
            )

            if self.previous_size_bytes is None:
                raise ValueError(
                    "El cambio debe conservar "
                    "previous_size_bytes"
                )

            if self.previous_size_bytes < 0:
                raise ValueError(
                    "previous_size_bytes no puede "
                    "ser negativo"
                )

        if (
            self.change_type
            == PromotionChangeType.MODIFIED
            and self.previous_sha256
            == self.current_sha256
        ):
            raise ValueError(
                "Un archivo modificado debe "
                "cambiar su hash"
            )

        if (
            self.change_type
            == PromotionChangeType.UNCHANGED
            and (
                self.previous_sha256
                != self.current_sha256
                or self.previous_size_bytes
                != self.current_size_bytes
            )
        ):
            raise ValueError(
                "Un archivo sin cambios debe "
                "conservar hash y tamano"
            )

        object.__setattr__(
            self,
            "relative_path",
            relative_path,
        )

    @staticmethod
    def _validate_sha256(
        value: str,
        field_name: str,
    ) -> None:
        if (
            not isinstance(value, str)
            or _SHA256_PATTERN.fullmatch(
                value
            )
            is None
        ):
            raise ValueError(
                f"{field_name} no es un "
                "SHA-256 valido"
            )


@dataclass(frozen=True, slots=True)
class PromotionPreview:
    workspace_path: str
    target_repository_root: str
    changes: tuple[
        PromotionFileChange,
        ...,
    ]
    preview_hash: str

    def __post_init__(self) -> None:
        workspace_path = (
            self.workspace_path.strip()
        )
        target_repository_root = (
            self.target_repository_root.strip()
        )

        if not workspace_path:
            raise ValueError(
                "workspace_path no puede estar "
                "vacio"
            )

        if not target_repository_root:
            raise ValueError(
                "target_repository_root no puede "
                "estar vacio"
            )

        if not self.changes:
            raise ValueError(
                "La vista previa debe contener "
                "archivos"
            )

        relative_paths = tuple(
            change.relative_path
            for change in self.changes
        )

        if (
            len(relative_paths)
            != len(set(relative_paths))
        ):
            raise ValueError(
                "La vista previa contiene rutas "
                "duplicadas"
            )

        if _SHA256_PATTERN.fullmatch(
            self.preview_hash
        ) is None:
            raise ValueError(
                "preview_hash no es un "
                "SHA-256 valido"
            )

        object.__setattr__(
            self,
            "workspace_path",
            workspace_path,
        )
        object.__setattr__(
            self,
            "target_repository_root",
            target_repository_root,
        )

    @property
    def added_count(self) -> int:
        return self._count(
            PromotionChangeType.ADDED
        )

    @property
    def modified_count(self) -> int:
        return self._count(
            PromotionChangeType.MODIFIED
        )

    @property
    def unchanged_count(self) -> int:
        return self._count(
            PromotionChangeType.UNCHANGED
        )

    @property
    def changed_count(self) -> int:
        return (
            self.added_count
            + self.modified_count
        )

    def _count(
        self,
        change_type: PromotionChangeType,
    ) -> int:
        return sum(
            change.change_type
            == change_type
            for change in self.changes
        )