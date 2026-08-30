from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from app.execution.git_repository import (
    GitRepositoryInspectionError,
    GitRepositoryInspector,
)
from app.execution.promotion_models import (
    PromotionChangeType,
    PromotionFileChange,
    PromotionPreview,
)
from app.execution.promotion_preview import (
    PromotionPreviewError,
    PromotionPreviewService,
)


class PromotionApplicationError(
    RuntimeError
):
    """No se pudo aplicar la promocion."""


@dataclass(frozen=True, slots=True)
class PromotionRollbackEntry:
    relative_path: str
    previous_content: bytes | None


@dataclass(frozen=True, slots=True)
class PromotionApplicationResult:
    repository_root: Path
    preview_hash: str
    branch_name: str
    head_commit: str
    written_paths: tuple[str, ...]
    added_count: int
    modified_count: int
    rollback_entries: tuple[
        PromotionRollbackEntry,
        ...,
    ]


class PromotionApplicationService:
    def __init__(
        self,
        preview_service: PromotionPreviewService,
        git_inspector: GitRepositoryInspector,
    ) -> None:
        self._preview_service = preview_service
        self._git_inspector = git_inspector

    def apply(
        self,
        preview: PromotionPreview,
        confirmed_preview_hash: str,
    ) -> PromotionApplicationResult:
        confirmed_hash = (
            confirmed_preview_hash.strip()
        )

        if (
            not confirmed_hash
            or confirmed_hash
            != preview.preview_hash
        ):
            raise PromotionApplicationError(
                "El hash confirmado no coincide "
                "con la vista previa"
            )

        workspace = Path(
            preview.workspace_path
        ).resolve()
        target_root = Path(
            preview.target_repository_root
        ).resolve()

        try:
            repository_state = (
                self._git_inspector.inspect(
                    target_root
                )
            )

            current_preview = (
                self._preview_service.create(
                    workspace_path=workspace,
                    target_repository_root=(
                        target_root
                    ),
                )
            )

        except (
            GitRepositoryInspectionError,
            PromotionPreviewError,
        ) as error:
            raise PromotionApplicationError(
                str(error)
            ) from error

        if (
            current_preview.preview_hash
            != preview.preview_hash
            or current_preview.preview_hash
            != confirmed_hash
        ):
            raise PromotionApplicationError(
                "El workspace o el repositorio "
                "han cambiado desde la vista previa"
            )

        if current_preview.changed_count == 0:
            raise PromotionApplicationError(
                "La vista previa no contiene "
                "cambios para aplicar"
            )

        (
            written_paths,
            rollback_entries,
        ) = self._apply_changes(
            workspace=workspace,
            target_root=target_root,
            changes=current_preview.changes,
        )

        try:
            final_state = (
                self._git_inspector.inspect(
                    repository_root=target_root,
                    require_clean=False,
                )
            )

        except GitRepositoryInspectionError as error:
            raise PromotionApplicationError(
                str(error)
            ) from error

        if (
            final_state.current_branch
            != repository_state.current_branch
            or final_state.head_commit
            != repository_state.head_commit
        ):
            raise PromotionApplicationError(
                "La rama o el commit del "
                "repositorio cambiaron durante "
                "la promocion"
            )

        return PromotionApplicationResult(
            repository_root=target_root,
            preview_hash=confirmed_hash,
            branch_name=(
                repository_state.current_branch
            ),
            head_commit=(
                repository_state.head_commit
            ),
            written_paths=written_paths,
            added_count=(
                current_preview.added_count
            ),
            modified_count=(
                current_preview.modified_count
            ),
            rollback_entries=rollback_entries,
        )

    def rollback(
        self,
        result: PromotionApplicationResult,
    ) -> None:
        root = result.repository_root.resolve()

        try:
            state = self._git_inspector.inspect(
                repository_root=root,
                require_clean=False,
            )

        except GitRepositoryInspectionError as error:
            raise PromotionApplicationError(
                str(error)
            ) from error

        if (
            state.current_branch
            != result.branch_name
            or state.head_commit
            != result.head_commit
        ):
            raise PromotionApplicationError(
                "La rama o el commit cambiaron "
                "antes del rollback"
            )

        added_targets: list[Path] = []

        try:
            for entry in reversed(
                result.rollback_entries
            ):
                relative = PurePosixPath(
                    entry.relative_path
                )
                target = root.joinpath(
                    *relative.parts
                )

                if (
                    not target.resolve()
                    .is_relative_to(root)
                    or target.is_symlink()
                ):
                    raise (
                        PromotionApplicationError(
                            "Una ruta de rollback "
                            "no es segura"
                        )
                    )

                if entry.previous_content is None:
                    if target.exists():
                        if not target.is_file():
                            raise (
                                PromotionApplicationError(
                                    "Una ruta nueva "
                                    "ya no es un "
                                    "archivo"
                                )
                            )

                        target.unlink()

                    added_targets.append(target)

                else:
                    if not target.parent.is_dir():
                        raise (
                            PromotionApplicationError(
                                "El directorio de "
                                "rollback no existe"
                            )
                        )

                    self._write_atomic(
                        target=target,
                        content=(
                            entry.previous_content
                        ),
                    )

            for target in added_targets:
                self._remove_empty_parents(
                    parent=target.parent,
                    target_root=root,
                )

            final_state = (
                self._git_inspector.inspect(
                    root
                )
            )

        except (
            OSError,
            GitRepositoryInspectionError,
        ) as error:
            raise PromotionApplicationError(
                "No se pudo restaurar la "
                "promocion"
            ) from error

        if (
            final_state.current_branch
            != result.branch_name
            or final_state.head_commit
            != result.head_commit
        ):
            raise PromotionApplicationError(
                "El rollback cambio la rama o "
                "el commit"
            )

    def _apply_changes(
        self,
        workspace: Path,
        target_root: Path,
        changes: tuple[
            PromotionFileChange,
            ...,
        ],
    ) -> tuple[
        tuple[str, ...],
        tuple[PromotionRollbackEntry, ...],
    ]:
        backups: dict[
            Path,
            bytes | None,
        ] = {}
        created_directories: list[Path] = []
        written_paths: list[str] = []

        try:
            for change in changes:
                if (
                    change.change_type
                    == PromotionChangeType
                    .UNCHANGED
                ):
                    continue

                relative = PurePosixPath(
                    change.relative_path
                )
                source = workspace.joinpath(
                    *relative.parts
                )
                target = target_root.joinpath(
                    *relative.parts
                )

                current_content = (
                    self._read_source(
                        source=source,
                        expected_sha256=(
                            change.current_sha256
                        ),
                    )
                )

                self._validate_target(
                    target=target,
                    target_root=target_root,
                    change=change,
                )

                created_directories.extend(
                    self._ensure_parent_directory(
                        parent=target.parent,
                        target_root=target_root,
                    )
                )

                backups[target] = (
                    target.read_bytes()
                    if target.exists()
                    else None
                )

                self._write_atomic(
                    target=target,
                    content=current_content,
                )

                written_paths.append(
                    change.relative_path
                )

        except Exception as error:
            self._rollback(
                backups=backups,
                created_directories=(
                    created_directories
                ),
            )

            if isinstance(
                error,
                PromotionApplicationError,
            ):
                raise

            raise PromotionApplicationError(
                "La promocion fallo y se "
                "restauro el repositorio"
            ) from error

        rollback_entries = tuple(
            PromotionRollbackEntry(
                relative_path=(
                    target.relative_to(
                        target_root
                    ).as_posix()
                ),
                previous_content=(
                    previous_content
                ),
            )
            for target, previous_content
            in backups.items()
        )

        return (
            tuple(written_paths),
            rollback_entries,
        )

    @staticmethod
    def _read_source(
        source: Path,
        expected_sha256: str,
    ) -> bytes:
        if (
            source.is_symlink()
            or not source.is_file()
        ):
            raise PromotionApplicationError(
                "Un archivo del workspace ya no "
                "es valido"
            )

        content = source.read_bytes()

        if (
            sha256(content).hexdigest()
            != expected_sha256
        ):
            raise PromotionApplicationError(
                "Un archivo del workspace cambio "
                "despues de la confirmacion"
            )

        return content

    @staticmethod
    def _validate_target(
        target: Path,
        target_root: Path,
        change: PromotionFileChange,
    ) -> None:
        resolved_target = target.resolve()

        if not resolved_target.is_relative_to(
            target_root
        ):
            raise PromotionApplicationError(
                "Una ruta sale del repositorio "
                "objetivo"
            )

        current = target

        while current != target_root:
            if current.is_symlink():
                raise PromotionApplicationError(
                    "El destino contiene un "
                    "enlace simbolico"
                )

            current = current.parent

        if (
            change.change_type
            == PromotionChangeType.ADDED
        ):
            if target.exists():
                raise PromotionApplicationError(
                    "Un archivo nuevo ya existe "
                    "en el destino"
                )

            return

        if not target.is_file():
            raise PromotionApplicationError(
                "El archivo que se quiere "
                "modificar ya no existe"
            )

        current_content = target.read_bytes()

        if (
            sha256(current_content).hexdigest()
            != change.previous_sha256
        ):
            raise PromotionApplicationError(
                "Un archivo del destino cambio "
                "despues de la confirmacion"
            )

    @staticmethod
    def _ensure_parent_directory(
        parent: Path,
        target_root: Path,
    ) -> tuple[Path, ...]:
        missing: list[Path] = []
        current = parent

        while current != target_root:
            if current.exists():
                if (
                    current.is_symlink()
                    or not current.is_dir()
                ):
                    raise (
                        PromotionApplicationError(
                            "Un directorio del "
                            "destino no es valido"
                        )
                    )

                break

            missing.append(current)
            current = current.parent

        created: list[Path] = []

        for directory in reversed(missing):
            directory.mkdir()
            created.append(directory)

        return tuple(created)

    def _write_atomic(
        self,
        target: Path,
        content: bytes,
    ) -> None:
        descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=".promotion-",
                suffix=".tmp",
                dir=target.parent,
            )
        )
        temporary_path = Path(
            temporary_name
        )

        try:
            with os.fdopen(
                descriptor,
                "wb",
            ) as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )

            os.replace(
                temporary_path,
                target,
            )

        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _remove_empty_parents(
        parent: Path,
        target_root: Path,
    ) -> None:
        current = parent

        while current != target_root:
            if (
                not current.exists()
                or any(current.iterdir())
            ):
                break

            current.rmdir()
            current = current.parent

    @staticmethod
    def _rollback(
        backups: dict[
            Path,
            bytes | None,
        ],
        created_directories: list[Path],
    ) -> None:
        for target, previous_content in reversed(
            tuple(backups.items())
        ):
            if previous_content is None:
                if target.exists():
                    target.unlink()
            else:
                target.write_bytes(
                    previous_content
                )

        for directory in reversed(
            created_directories
        ):
            if (
                directory.exists()
                and not any(
                    directory.iterdir()
                )
            ):
                directory.rmdir()