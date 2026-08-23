from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.context.git_commit_repository import (
    GitCommitRepository,
)


class GitSynchronizationError(RuntimeError):
    """Error controlado al consultar Git."""


@dataclass(frozen=True, slots=True)
class GitCommitSyncResult:
    scanned: int
    created: int
    updated: int
    unchanged: int


class GitCommitSynchronizer:
    FIELD_SEPARATOR = "\x1f"
    RECORD_SEPARATOR = "\x1e"

    def __init__(
        self,
        repository: GitCommitRepository,
        project_id: int,
        project_root: Path,
    ) -> None:
        self._repository = repository
        self._project_id = project_id
        self._project_root = (
            project_root.resolve()
        )

    def synchronize(
        self,
    ) -> GitCommitSyncResult:
        git_root = self._find_git_root()

        try:
            relative_project_path = (
                self._project_root
                .relative_to(git_root)
                .as_posix()
            )
        except ValueError as error:
            raise GitSynchronizationError(
                "El proyecto no está dentro "
                "del repositorio Git"
            ) from error

        output = self._run_git_log(
            git_root=git_root,
            relative_project_path=(
                relative_project_path
            ),
        )

        records = self._parse_log(output)

        created = 0
        updated = 0
        unchanged = 0

        for record in records:
            existing = (
                self._repository.get_by_hash(
                    record["commit_hash"]
                )
            )

            if (
                existing is not None
                and self._is_unchanged(
                    existing=existing,
                    record=record,
                )
            ):
                unchanged += 1
                continue

            self._repository.save(
                commit_hash=record["commit_hash"],
                project_id=self._project_id,
                parent_hash=record["parent_hash"],
                author_name=record["author_name"],
                authored_at=record["authored_at"],
                subject=record["subject"],
                body=record["body"],
            )

            if existing is None:
                created += 1
            else:
                updated += 1

        return GitCommitSyncResult(
            scanned=len(records),
            created=created,
            updated=updated,
            unchanged=unchanged,
        )

    def _find_git_root(self) -> Path:
        result = self._run_git(
            [
                "-C",
                str(self._project_root),
                "rev-parse",
                "--show-toplevel",
            ]
        )

        root_value = result.stdout.strip()

        if not root_value:
            raise GitSynchronizationError(
                "Git no devolvió la raíz "
                "del repositorio"
            )

        return Path(root_value).resolve()

    def _run_git_log(
        self,
        git_root: Path,
        relative_project_path: str,
    ) -> str:
        format_value = (
            "%H%x1f"
            "%P%x1f"
            "%an%x1f"
            "%aI%x1f"
            "%s%x1f"
            "%b%x1e"
        )

        result = self._run_git(
            [
                "-C",
                str(git_root),
                "log",
                f"--format={format_value}",
                "--",
                relative_project_path,
            ]
        )

        return result.stdout

    @staticmethod
    def _run_git(
        arguments: list[str],
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *arguments],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as error:
            raise GitSynchronizationError(
                "No se encontró el ejecutable Git"
            ) from error
        except subprocess.CalledProcessError as error:
            detail = (
                error.stderr.strip()
                or error.stdout.strip()
                or "error desconocido"
            )

            raise GitSynchronizationError(
                f"Git no pudo completar "
                f"la operación: {detail}"
            ) from error

    def _parse_log(
        self,
        output: str,
    ) -> list[dict[str, str | None]]:
        records = []

        for raw_record in output.split(
            self.RECORD_SEPARATOR
        ):
            raw_record = raw_record.strip(
                "\r\n"
            )

            if not raw_record:
                continue

            fields = raw_record.split(
                self.FIELD_SEPARATOR,
                maxsplit=5,
            )

            if len(fields) != 6:
                raise GitSynchronizationError(
                    "Git devolvió un registro "
                    "con formato inesperado"
                )

            (
                commit_hash,
                parent_hash,
                author_name,
                authored_at,
                subject,
                body,
            ) = fields

            records.append(
                {
                    "commit_hash": (
                        commit_hash.strip()
                    ),
                    "parent_hash": (
                        parent_hash.strip()
                        or None
                    ),
                    "author_name": (
                        author_name.strip()
                        or None
                    ),
                    "authored_at": (
                        authored_at.strip()
                    ),
                    "subject": subject.strip(),
                    "body": body.strip() or None,
                }
            )

        return records

    def _is_unchanged(
        self,
        existing: object,
        record: dict[str, str | None],
    ) -> bool:
        return (
            existing.project_id
            == self._project_id
            and existing.parent_hash
            == record["parent_hash"]
            and existing.author_name
            == record["author_name"]
            and existing.authored_at
            == record["authored_at"]
            and existing.subject
            == record["subject"]
            and existing.body
            == record["body"]
        )