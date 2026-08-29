from __future__ import annotations

from datetime import datetime


def elapsed_seconds_between(
    started_at: str | None,
    finished_at: str | None,
) -> float | None:
    if (
        started_at is None
        or finished_at is None
    ):
        return None

    try:
        started = datetime.fromisoformat(
            started_at.strip().replace(
                "Z",
                "+00:00",
            )
        )
        finished = datetime.fromisoformat(
            finished_at.strip().replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    elapsed_seconds = (
        finished - started
    ).total_seconds()

    if elapsed_seconds < 0:
        return None

    return elapsed_seconds


def format_elapsed_seconds(
    started_at: str | None,
    finished_at: str | None,
) -> str:
    elapsed_seconds = elapsed_seconds_between(
        started_at=started_at,
        finished_at=finished_at,
    )

    if elapsed_seconds is None:
        return "no disponible"

    return f"{elapsed_seconds:.3f} s"