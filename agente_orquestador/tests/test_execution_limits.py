import pytest

from app.execution.limits import (
    ExecutionLimits,
)


def test_uses_safe_default_limits() -> None:
    limits = ExecutionLimits()

    assert limits.max_actions == 100
    assert (
        limits.max_text_file_bytes
        == 1_000_000
    )
    assert (
        limits.max_output_characters
        == 20_000
    )
    assert (
        limits.command_timeout_seconds
        == 60.0
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "max_actions",
        "max_text_file_bytes",
        "max_output_characters",
        "command_timeout_seconds",
    ),
)
def test_rejects_non_positive_limit(
    field_name: str,
) -> None:
    values = {
        "max_actions": 100,
        "max_text_file_bytes": 1_000_000,
        "max_output_characters": 20_000,
        "command_timeout_seconds": 60.0,
    }
    values[field_name] = 0

    with pytest.raises(ValueError):
        ExecutionLimits(**values)