from __future__ import annotations

from sandbox_gateway.api import create_app
from sandbox_gateway.docker_runner import (
    DockerSandboxRunner,
)
from sandbox_gateway.service import (
    SandboxGatewayService,
)
from sandbox_gateway.settings import (
    GatewaySettings,
)
from sandbox_gateway.workspace import (
    GatewayWorkspace,
)


settings = GatewaySettings.load()

settings.temporary_root.mkdir(
    parents=True,
    exist_ok=True,
)

container_runner = DockerSandboxRunner(
    image=settings.docker_image,
    limits=settings.limits,
)

service = SandboxGatewayService(
    limits=settings.limits,
    workspace_manager=GatewayWorkspace(
        temporary_root=(
            settings.temporary_root
        )
    ),
    container_runner=container_runner,
)

app = create_app(
    service=service,
    auth_token=settings.auth_token,
)