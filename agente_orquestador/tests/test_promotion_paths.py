import pytest

from app.execution.promotion_paths import (
    PromotionPathError,
    map_source_to_target,
    map_target_to_source,
    normalize_target_subdirectory,
)


@pytest.mark.parametrize(
    (
        "value",
        "expected",
    ),
    (
        (".", "."),
        (
            "puntuacion_padel",
            "puntuacion_padel",
        ),
        (
            "proyectos/puntuacion_padel",
            "proyectos/puntuacion_padel",
        ),
        (
            "  puntuacion_padel  ",
            "puntuacion_padel",
        ),
    ),
)
def test_normalizes_target_subdirectory(
    value: str,
    expected: str,
) -> None:
    assert (
        normalize_target_subdirectory(value)
        == expected
    )


@pytest.mark.parametrize(
    "value",
    (
        "",
        "   ",
        "../fuera",
        "proyectos/../../fuera",
        "/ruta/absoluta",
        r"C:\ruta\absoluta",
        r"proyectos\destino",
    ),
)
def test_rejects_unsafe_target_subdirectory(
    value: str,
) -> None:
    with pytest.raises(
        PromotionPathError
    ):
        normalize_target_subdirectory(
            value
        )


def test_maps_source_to_repository_root(
) -> None:
    assert (
        map_source_to_target(
            source_relative_path="suma.py",
            target_subdirectory=".",
        )
        == "suma.py"
    )


def test_maps_source_to_project_directory(
) -> None:
    assert (
        map_source_to_target(
            source_relative_path=(
                "tests/test_suma.py"
            ),
            target_subdirectory=(
                "puntuacion_padel"
            ),
        )
        == (
            "puntuacion_padel/"
            "tests/test_suma.py"
        )
    )


@pytest.mark.parametrize(
    "source_relative_path",
    (
        "",
        ".",
        "../suma.py",
        "/suma.py",
        r"C:\suma.py",
        r"tests\test_suma.py",
    ),
)
def test_rejects_unsafe_source_path(
    source_relative_path: str,
) -> None:
    with pytest.raises(
        PromotionPathError
    ):
        map_source_to_target(
            source_relative_path=(
                source_relative_path
            ),
            target_subdirectory=(
                "puntuacion_padel"
            ),
        )


def test_maps_target_back_to_source(
) -> None:
    assert (
        map_target_to_source(
            target_relative_path=(
                "puntuacion_padel/"
                "tests/test_suma.py"
            ),
            target_subdirectory=(
                "puntuacion_padel"
            ),
        )
        == "tests/test_suma.py"
    )


def test_maps_root_target_back_to_source(
) -> None:
    assert (
        map_target_to_source(
            target_relative_path=(
                "tests/test_suma.py"
            ),
            target_subdirectory=".",
        )
        == "tests/test_suma.py"
    )


def test_rejects_target_outside_project(
) -> None:
    with pytest.raises(
        PromotionPathError,
        match="no pertenece",
    ):
        map_target_to_source(
            target_relative_path=(
                "otro_proyecto/suma.py"
            ),
            target_subdirectory=(
                "puntuacion_padel"
            ),
        )