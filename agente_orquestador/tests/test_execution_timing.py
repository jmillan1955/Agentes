import pytest

from app.execution.timing import (
    elapsed_seconds_between,
    format_elapsed_seconds,
)


def test_calculates_elapsed_seconds(
) -> None:
    result = elapsed_seconds_between(
        started_at=(
            "2026-08-29T07:00:00.100Z"
        ),
        finished_at=(
            "2026-08-29T07:00:01.350Z"
        ),
    )

    assert result == pytest.approx(1.25)


@pytest.mark.parametrize(
    (
        "started_at",
        "finished_at",
    ),
    (
        (None, None),
        (
            "2026-08-29T07:00:00.000Z",
            None,
        ),
        (
            "fecha-invalida",
            "2026-08-29T07:00:00.000Z",
        ),
        (
            "2026-08-29T07:00:02.000Z",
            "2026-08-29T07:00:01.000Z",
        ),
    ),
)
def test_returns_none_when_unavailable(
    started_at: str | None,
    finished_at: str | None,
) -> None:
    assert (
        elapsed_seconds_between(
            started_at=started_at,
            finished_at=finished_at,
        )
        is None
    )


def test_formats_elapsed_seconds() -> None:
    assert format_elapsed_seconds(
        started_at=(
            "2026-08-29T07:00:00.100Z"
        ),
        finished_at=(
            "2026-08-29T07:00:01.350Z"
        ),
    ) == "1.250 s"


def test_formats_unavailable_duration(
) -> None:
    assert format_elapsed_seconds(
        started_at=None,
        finished_at=None,
    ) == "no disponible"