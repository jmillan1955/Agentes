from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.execution.promotion_query import (
    PromotionQueryError,
    PromotionQueryService,
)


def test_gets_promotion_by_id() -> None:
    repository = Mock()
    promotion = SimpleNamespace(
        id=8
    )

    repository.get_by_id.return_value = (
        promotion
    )

    service = PromotionQueryService(
        promotion_repository=repository
    )

    result = service.get_by_id(8)

    assert result is promotion

    repository.get_by_id.assert_called_once_with(
        8
    )


@pytest.mark.parametrize(
    "promotion_id",
    (
        0,
        -1,
    ),
)
def test_rejects_invalid_promotion_id(
    promotion_id: int,
) -> None:
    repository = Mock()

    service = PromotionQueryService(
        promotion_repository=repository
    )

    with pytest.raises(
        PromotionQueryError,
        match="mayor que cero",
    ):
        service.get_by_id(
            promotion_id
        )

    repository.get_by_id.assert_not_called()


def test_reports_missing_promotion() -> None:
    repository = Mock()

    repository.get_by_id.return_value = None

    service = PromotionQueryService(
        promotion_repository=repository
    )

    with pytest.raises(
        PromotionQueryError,
        match="No existe la promocion #8",
    ):
        service.get_by_id(8)

    repository.get_by_id.assert_called_once_with(
        8
    )