from pathlib import Path

import pytest

from app.context import ContextDatabase
from app.execution.factory import (
    ExecutionRuntime,
    create_execution_runtime,
)
from app.execution.runner import (
    ExecutionRunner,
)
from app.execution.service import (
    ExecutionPreparationService,
)
from app.execution.query import (
    ExecutionQueryService,
)
from app.execution.manifest_service import (
    ExecutionManifestService,
)
from unittest.mock import Mock
from app.execution.action_generator import (
    ExecutionActionGenerator,
)

def test_creates_runtime_without_gateway(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        runtime = create_execution_runtime(
            database=database,
            language_provider=Mock(),
            execution_workspace_root=(
                tmp_path / "executions"
            ),
            protected_project_root=(
                tmp_path / "orchestrator"
            ),
            sandbox_gateway_url=None,
            sandbox_gateway_token=None,
            sandbox_gateway_timeout_seconds=(
                150
            ),
        )

        assert isinstance(
            runtime,
            ExecutionRuntime,
        )
        assert isinstance(
            runtime.preparation_service,
            ExecutionPreparationService,
        )
        assert isinstance(
            runtime.query_service,
            ExecutionQueryService,
        )
        assert isinstance(
            runtime.manifest_service,
            ExecutionManifestService,
        )
        assert isinstance(
            runtime.action_generator,
            ExecutionActionGenerator,
        )
        assert isinstance(
            runtime.runner,
            ExecutionRunner,
        )
        assert runtime.sandbox_enabled is False


def test_creates_runtime_with_gateway(
    tmp_path: Path,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        runtime = create_execution_runtime(
            database=database,
            language_provider=Mock(),
            execution_workspace_root=(
                tmp_path / "executions"
            ),
            protected_project_root=(
                tmp_path / "orchestrator"
            ),
            sandbox_gateway_url=(
                "http://192.168.1.102:8091"
            ),
            sandbox_gateway_token=(
                "token-seguro-de-prueba-"
                "1234567890"
            ),
            sandbox_gateway_timeout_seconds=(
                150
            ),
        )

        assert runtime.sandbox_enabled is True


@pytest.mark.parametrize(
    (
        "gateway_url",
        "gateway_token",
    ),
    (
        (
            "http://192.168.1.102:8091",
            None,
        ),
        (
            None,
            (
                "token-seguro-de-prueba-"
                "1234567890"
            ),
        ),
    ),
)
def test_rejects_incomplete_gateway_configuration(
    tmp_path: Path,
    gateway_url: str | None,
    gateway_token: str | None,
) -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        with pytest.raises(
            ValueError,
            match=(
                "La URL y el token del gateway "
                "deben configurarse juntos"
            ),
        ):
            create_execution_runtime(
                database=database,
                language_provider=Mock(),
                execution_workspace_root=(
                    tmp_path / "executions"
                ),
                protected_project_root=(
                    tmp_path / "orchestrator"
                ),
                sandbox_gateway_url=(
                    gateway_url
                ),
                sandbox_gateway_token=(
                    gateway_token
                ),
                sandbox_gateway_timeout_seconds=(
                    150
                ),
            )