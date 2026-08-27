from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox_gateway.models import (
    PytestJobRequest,
)


class GatewayWorkspace:
    def __init__(
        self,
        temporary_root: Path | None = None,
    ) -> None:
        self._temporary_root = (
            temporary_root.resolve()
            if temporary_root is not None
            else None
        )

    @contextmanager
    def materialize(
        self,
        request: PytestJobRequest,
    ) -> Iterator[Path]:
        root_value = (
            str(self._temporary_root)
            if self._temporary_root
            is not None
            else None
        )

        with TemporaryDirectory(
            prefix="orchestrator-sandbox-",
            dir=root_value,
        ) as temporary_directory:
            workspace = Path(
                temporary_directory
            ).resolve()

            for file_payload in request.files:
                target = (
                    workspace
                    / file_payload.relative_path
                ).resolve()

                if not target.is_relative_to(
                    workspace
                ):
                    raise ValueError(
                        "Un archivo queda fuera "
                        "del workspace temporal"
                    )

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                target.write_bytes(
                    file_payload.decode()
                )

                target.chmod(0o644)

            for directory in sorted(
                (
                    path
                    for path in workspace.rglob(
                        "*"
                    )
                    if path.is_dir()
                ),
                key=lambda path: len(
                    path.parts
                ),
                reverse=True,
            ):
                directory.chmod(0o755)

            workspace.chmod(0o755)

            yield workspace