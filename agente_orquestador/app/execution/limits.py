from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_actions: int = 100
    max_text_file_bytes: int = 1_000_000
    max_output_characters: int = 20_000
    command_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        integer_limits = (
            "max_actions",
            "max_text_file_bytes",
            "max_output_characters",
        )

        for field_name in integer_limits:
            value = getattr(
                self,
                field_name,
            )

            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero"
                )

        if self.command_timeout_seconds <= 0:
            raise ValueError(
                "command_timeout_seconds debe "
                "ser mayor que cero"
            )