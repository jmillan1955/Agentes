from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from app.context.document_repository import (
    DocumentRepository,
)


@dataclass(frozen=True, slots=True)
class DocumentSyncResult:
    scanned: int
    created: int
    updated: int
    unchanged: int
    deleted: int


class DocumentSynchronizer:
    def __init__(
        self,
        repository: DocumentRepository,
        project_id: int,
        project_root: Path,
        documents_directory: str = "docs",
    ) -> None:
        self._repository = repository
        self._project_id = project_id
        self._project_root = (
            project_root.resolve()
        )
        self._documents_root = (
            self._project_root
            / documents_directory
        ).resolve()

        try:
            self._documents_root.relative_to(
                self._project_root
            )
        except ValueError as error:
            raise ValueError(
                "La carpeta de documentos debe "
                "estar dentro del proyecto"
            ) from error

    def synchronize(
        self,
    ) -> DocumentSyncResult:
        if not self._documents_root.is_dir():
            raise FileNotFoundError(
                "No existe la carpeta de documentos: "
                f"{self._documents_root}"
            )

        markdown_files = sorted(
            path
            for path in self._documents_root.rglob(
                "*.md"
            )
            if path.is_file()
        )

        current_paths: set[str] = set()
        created = 0
        updated = 0
        unchanged = 0

        for document_path in markdown_files:
            relative_path = (
                document_path
                .relative_to(self._project_root)
                .as_posix()
            )

            current_paths.add(relative_path)

            content = document_path.read_text(
                encoding="utf-8-sig"
            )

            content_hash = sha256(
                content.encode("utf-8")
            ).hexdigest()

            existing = self._repository.get_by_path(
                project_id=self._project_id,
                relative_path=relative_path,
            )

            if (
                existing is not None
                and existing.content_hash
                == content_hash
            ):
                unchanged += 1
                continue

            title = self._extract_title(
                content=content,
                fallback=document_path.stem,
            )

            modified_at = datetime.fromtimestamp(
                document_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat()

            self._repository.save(
                project_id=self._project_id,
                relative_path=relative_path,
                title=title,
                content=content,
                content_hash=content_hash,
                file_modified_at=modified_at,
            )

            if existing is None:
                created += 1
            else:
                updated += 1

        deleted = self._delete_missing(
            current_paths=current_paths
        )

        return DocumentSyncResult(
            scanned=len(markdown_files),
            created=created,
            updated=updated,
            unchanged=unchanged,
            deleted=deleted,
        )

    def _delete_missing(
        self,
        current_paths: set[str],
    ) -> int:
        documents_prefix = (
            self._documents_root
            .relative_to(self._project_root)
            .as_posix()
            .rstrip("/")
            + "/"
        )

        stored_documents = (
            self._repository.list_by_project(
                self._project_id
            )
        )

        deleted = 0

        for document in stored_documents:
            if not document.relative_path.startswith(
                documents_prefix
            ):
                continue

            if (
                document.relative_path
                in current_paths
            ):
                continue

            if self._repository.delete(
                project_id=self._project_id,
                relative_path=(
                    document.relative_path
                ),
            ):
                deleted += 1

        return deleted

    @staticmethod
    def _extract_title(
        content: str,
        fallback: str,
    ) -> str:
        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("# "):
                title = stripped[2:].strip()

                if title:
                    return title

        return fallback.replace(
            "_",
            " ",
        ).strip()