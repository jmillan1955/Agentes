import base64
from pathlib import Path

from sandbox_gateway.models import (
    PytestJobRequest,
    SandboxFilePayload,
)
from sandbox_gateway.workspace import (
    GatewayWorkspace,
)


def create_request() -> PytestJobRequest:
    content = (
        b"def test_temporal():\n"
        b"    assert True\n"
    )

    return PytestJobRequest(
        files=(
            SandboxFilePayload(
                relative_path=(
                    "tests/test_temporal.py"
                ),
                content_base64=(
                    base64.b64encode(
                        content
                    ).decode("ascii")
                ),
            ),
        ),
        test_target="tests",
        timeout_seconds=60.0,
        max_output_characters=20_000,
    )


def test_materializes_and_removes_workspace(
    tmp_path: Path,
) -> None:
    manager = GatewayWorkspace(
        temporary_root=tmp_path
    )

    with manager.materialize(
        create_request()
    ) as workspace:
        assert workspace.is_dir()

        target = (
            workspace
            / "tests"
            / "test_temporal.py"
        )

        assert target.read_text(
            encoding="utf-8"
        ) == (
            "def test_temporal():\n"
            "    assert True\n"
        )

        stored_workspace = workspace

    assert stored_workspace.exists() is False


def test_does_not_modify_source_payload(
    tmp_path: Path,
) -> None:
    request = create_request()
    original = (
        request.files[0].content_base64
    )

    manager = GatewayWorkspace(
        temporary_root=tmp_path
    )

    with manager.materialize(request):
        pass

    assert (
        request.files[0].content_base64
        == original
    )