from __future__ import annotations

import base64
import json
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path, PurePosixPath

from app.execution.promotion_models import (
    PromotionChangeType,
    PromotionFileChange,
    PromotionPreview,
)
from app.execution.workspace_package import (
    WorkspacePackager,
    WorkspacePackagingError,
)
from app.execution.promotion_paths import (
    PromotionPathError,
    map_source_to_target,
    normalize_target_subdirectory,
)

class PromotionPreviewError(
    RuntimeError
):
    """No se pudo generar la vista previa."""


class PromotionPreviewService:
    def __init__(
        self,
        workspace_packager: WorkspacePackager,
    ) -> None:
        self._workspace_packager = (
            workspace_packager
        )

    def create(
        self,
        workspace_path: Path,
        target_repository_root: Path,
        target_subdirectory: str = ".",
    ) -> PromotionPreview:
        workspace_input = (
            workspace_path.expanduser()
        )
        target_input = (
            target_repository_root.expanduser()
        )

        if workspace_input.is_symlink():
            raise PromotionPreviewError(
                "El workspace no puede ser un "
                "enlace simbolico"
            )

        if target_input.is_symlink():
            raise PromotionPreviewError(
                "El repositorio objetivo no puede "
                "ser un enlace simbolico"
            )

        workspace = workspace_input.resolve()
        target_root = target_input.resolve()
        try:
            normalized_target_subdirectory = (
                normalize_target_subdirectory(
                    target_subdirectory
                )
            )

        except PromotionPathError as error:
            raise PromotionPreviewError(
                str(error)
            ) from error

        self._validate_roots(
            workspace=workspace,
            target_root=target_root,
        )

        try:
            packaged_files = (
                self._workspace_packager
                .package(workspace)
            )

        except WorkspacePackagingError as error:
            raise PromotionPreviewError(
                str(error)
            ) from error

        changes = tuple(
            self._create_file_change(
                target_root=target_root,
                relative_path=(
                    map_source_to_target(
                        source_relative_path=(
                            packaged_file
                            .relative_path
                        ),
                        target_subdirectory=(
                            normalized_target_subdirectory
                        ),
                    )
                ),                current_content=(
                    base64.b64decode(
                        packaged_file
                        .content_base64,
                        validate=True,
                    )
                ),
            )
            for packaged_file in packaged_files
        )

        preview_hash = (
            self._calculate_preview_hash(
                changes
            )
        )

        return PromotionPreview(
            workspace_path=str(workspace),
            target_repository_root=(
                str(target_root)
            ),
            changes=changes,
            preview_hash=preview_hash,
            target_subdirectory=(
                normalized_target_subdirectory
            ),
        )

    @staticmethod
    def _validate_roots(
        workspace: Path,
        target_root: Path,
    ) -> None:
        if not workspace.is_dir():
            raise PromotionPreviewError(
                "El workspace no existe"
            )

        if not target_root.is_dir():
            raise PromotionPreviewError(
                "El repositorio objetivo no existe"
            )

        git_metadata = target_root / ".git"

        if not git_metadata.exists():
            raise PromotionPreviewError(
                "El destino no es un repositorio "
                "Git"
            )

        if (
            workspace == target_root
            or workspace.is_relative_to(
                target_root
            )
            or target_root.is_relative_to(
                workspace
            )
        ):
            raise PromotionPreviewError(
                "El workspace y el repositorio "
                "objetivo deben estar separados"
            )

    def _create_file_change(
        self,
        target_root: Path,
        relative_path: str,
        current_content: bytes,
    ) -> PromotionFileChange:
        relative = PurePosixPath(
            relative_path
        )

        target_path = target_root.joinpath(
            *relative.parts
        )
        resolved_target = (
            target_path.resolve()
        )

        if not resolved_target.is_relative_to(
            target_root
        ):
            raise PromotionPreviewError(
                "Una ruta del destino sale del "
                "repositorio objetivo"
            )

        if target_path.is_symlink():
            raise PromotionPreviewError(
                "El destino contiene un enlace "
                "simbolico"
            )

        current_sha256 = sha256(
            current_content
        ).hexdigest()

        if not target_path.exists():
            change_type = (
                PromotionChangeType.ADDED
            )
            previous_content = None
            previous_sha256 = None
            previous_size_bytes = None

        else:
            if not target_path.is_file():
                raise PromotionPreviewError(
                    "Una ruta del destino no es "
                    "un archivo"
                )

            previous_content = (
                target_path.read_bytes()
            )
            previous_sha256 = sha256(
                previous_content
            ).hexdigest()
            previous_size_bytes = len(
                previous_content
            )

            if (
                previous_content
                == current_content
            ):
                change_type = (
                    PromotionChangeType
                    .UNCHANGED
                )
            else:
                change_type = (
                    PromotionChangeType
                    .MODIFIED
                )

        diff_text = self._create_diff(
            relative_path=relative_path,
            previous_content=previous_content,
            current_content=current_content,
        )

        return PromotionFileChange(
            relative_path=relative_path,
            change_type=change_type,
            previous_sha256=previous_sha256,
            current_sha256=current_sha256,
            previous_size_bytes=(
                previous_size_bytes
            ),
            current_size_bytes=len(
                current_content
            ),
            diff_text=diff_text,
        )

    @staticmethod
    def _create_diff(
        relative_path: str,
        previous_content: bytes | None,
        current_content: bytes,
    ) -> str:
        try:
            previous_text = (
                ""
                if previous_content is None
                else previous_content.decode(
                    "utf-8"
                )
            )
            current_text = (
                current_content.decode(
                    "utf-8"
                )
            )

        except UnicodeDecodeError as error:
            raise PromotionPreviewError(
                "La promocion solo admite "
                "archivos UTF-8"
            ) from error

        if previous_text == current_text:
            return ""

        return "".join(
            unified_diff(
                previous_text.splitlines(
                    keepends=True
                ),
                current_text.splitlines(
                    keepends=True
                ),
                fromfile=(
                    f"a/{relative_path}"
                ),
                tofile=f"b/{relative_path}",
            )
        )

    @staticmethod
    def _calculate_preview_hash(
        changes: tuple[
            PromotionFileChange,
            ...,
        ],
    ) -> str:
        canonical_changes = [
            {
                "relative_path": (
                    change.relative_path
                ),
                "change_type": (
                    change.change_type.value
                ),
                "previous_sha256": (
                    change.previous_sha256
                ),
                "current_sha256": (
                    change.current_sha256
                ),
                "previous_size_bytes": (
                    change.previous_size_bytes
                ),
                "current_size_bytes": (
                    change.current_size_bytes
                ),
            }
            for change in changes
        ]

        canonical_json = json.dumps(
            canonical_changes,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return sha256(
            canonical_json.encode("utf-8")
        ).hexdigest()