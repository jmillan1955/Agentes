from __future__ import annotations

from pathlib import (
    PurePosixPath,
    PureWindowsPath,
)


class PromotionPathError(
    ValueError
):
    """Una ruta de promocion no es segura."""


def normalize_target_subdirectory(
    target_subdirectory: str,
) -> str:
    normalized = target_subdirectory.strip()

    if not normalized:
        raise PromotionPathError(
            "target_subdirectory no puede "
            "estar vacio"
        )

    if normalized == ".":
        return normalized

    _validate_relative_path(
        relative_path=normalized,
        field_name="target_subdirectory",
    )

    return PurePosixPath(
        normalized
    ).as_posix()


def map_source_to_target(
    source_relative_path: str,
    target_subdirectory: str,
) -> str:
    source = _normalize_file_path(
        relative_path=source_relative_path,
        field_name="source_relative_path",
    )
    target_directory = (
        normalize_target_subdirectory(
            target_subdirectory
        )
    )

    if target_directory == ".":
        return source

    return (
        PurePosixPath(target_directory)
        .joinpath(source)
        .as_posix()
    )


def map_target_to_source(
    target_relative_path: str,
    target_subdirectory: str,
) -> str:
    target = _normalize_file_path(
        relative_path=target_relative_path,
        field_name="target_relative_path",
    )
    target_directory = (
        normalize_target_subdirectory(
            target_subdirectory
        )
    )

    if target_directory == ".":
        return target

    target_path = PurePosixPath(target)
    directory_path = PurePosixPath(
        target_directory
    )

    try:
        source_path = target_path.relative_to(
            directory_path
        )

    except ValueError as error:
        raise PromotionPathError(
            "La ruta destino no pertenece al "
            "subdirectorio autorizado"
        ) from error

    if str(source_path) == ".":
        raise PromotionPathError(
            "La ruta destino debe identificar "
            "un archivo"
        )

    return source_path.as_posix()


def _normalize_file_path(
    relative_path: str,
    field_name: str,
) -> str:
    normalized = relative_path.strip()

    _validate_relative_path(
        relative_path=normalized,
        field_name=field_name,
    )

    if normalized == ".":
        raise PromotionPathError(
            f"{field_name} debe identificar "
            "un archivo"
        )

    return PurePosixPath(
        normalized
    ).as_posix()


def _validate_relative_path(
    relative_path: str,
    field_name: str,
) -> None:
    if not relative_path:
        raise PromotionPathError(
            f"{field_name} no puede estar vacio"
        )

    posix_path = PurePosixPath(
        relative_path
    )
    windows_path = PureWindowsPath(
        relative_path
    )

    if (
        "\\" in relative_path
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise PromotionPathError(
            f"{field_name} no es segura"
        )