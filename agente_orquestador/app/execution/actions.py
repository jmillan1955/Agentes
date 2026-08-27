from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionActionType(str, Enum):
    CREATE_DIRECTORY = "create_directory"
    WRITE_TEXT_FILE = "write_text_file"
    RUN_PYTEST = "run_pytest"


@dataclass(frozen=True, slots=True)
class ExecutionAction:
    step_number: int
    name: str
    action_type: ExecutionActionType
    relative_path: str
    content: str | None = None

    def __post_init__(self) -> None:
        if self.step_number <= 0:
            raise ValueError(
                "step_number debe ser "
                "mayor que cero"
            )

        name = self.name.strip()
        relative_path = (
            self.relative_path.strip()
        )

        if not name:
            raise ValueError(
                "name no puede estar vacio"
            )

        if not relative_path:
            raise ValueError(
                "relative_path no puede "
                "estar vacio"
            )

        if (
            self.action_type
            == ExecutionActionType
            .CREATE_DIRECTORY
            and self.content is not None
        ):
            raise ValueError(
                "create_directory no admite "
                "contenido"
            )

        if (
            self.action_type
            == ExecutionActionType
            .WRITE_TEXT_FILE
            and self.content is None
        ):
            raise ValueError(
                "write_text_file requiere "
                "contenido"
            )
        if (
            self.action_type
            == ExecutionActionType.RUN_PYTEST
            and self.content is not None
        ):
            raise ValueError(
                "run_pytest no admite "
                "contenido"
            )
        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "relative_path",
            relative_path,
        )