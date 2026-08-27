from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sandbox_gateway.models import (
    GatewayLimits,
)
from tempfile import gettempdir

@dataclass(frozen=True, slots=True)
class GatewaySettings:
    auth_token: str
    docker_image: str
    temporary_root: Path
    host: str
    port: int
    limits: GatewayLimits

    @classmethod
    def load(cls) -> "GatewaySettings":
        auth_token = os.getenv(
            "SANDBOX_GATEWAY_TOKEN",
            "",
        ).strip()

        if len(auth_token) < 32:
            raise RuntimeError(
                "SANDBOX_GATEWAY_TOKEN debe "
                "tener al menos 32 caracteres"
            )

        docker_image = os.getenv(
            "SANDBOX_DOCKER_IMAGE",
            "orchestrator-pytest:3.12",
        ).strip()

        if not docker_image:
            raise RuntimeError(
                "SANDBOX_DOCKER_IMAGE no puede "
                "estar vacia"
            )

        temporary_root_value = os.getenv(
            "SANDBOX_TEMPORARY_ROOT",
            "",
        ).strip()

        if temporary_root_value:
            temporary_root = Path(
                temporary_root_value
            )

        else:
            temporary_root = (
                Path(gettempdir())
                / "orchestrator-sandbox"
                / "jobs"
            )

        if not temporary_root.is_absolute():
            raise RuntimeError(
                "SANDBOX_TEMPORARY_ROOT debe "
                "ser absoluta"
            )

        host = os.getenv(
            "SANDBOX_GATEWAY_HOST",
            "0.0.0.0",
        ).strip()

        if not host:
            raise RuntimeError(
                "SANDBOX_GATEWAY_HOST no puede "
                "estar vacio"
            )

        port_value = os.getenv(
            "SANDBOX_GATEWAY_PORT",
            "8091",
        ).strip()

        try:
            port = int(port_value)

        except ValueError as error:
            raise RuntimeError(
                "SANDBOX_GATEWAY_PORT debe "
                "ser un entero"
            ) from error

        if not 1 <= port <= 65535:
            raise RuntimeError(
                "SANDBOX_GATEWAY_PORT queda "
                "fuera de rango"
            )

        limits = GatewayLimits(
            max_files=int(
                os.getenv(
                    "SANDBOX_MAX_FILES",
                    "200",
                )
            ),
            max_total_bytes=int(
                os.getenv(
                    "SANDBOX_MAX_TOTAL_BYTES",
                    "10000000",
                )
            ),
            max_timeout_seconds=float(
                os.getenv(
                    "SANDBOX_MAX_TIMEOUT_SECONDS",
                    "120",
                )
            ),
            max_output_characters=int(
                os.getenv(
                    "SANDBOX_MAX_OUTPUT_CHARACTERS",
                    "50000",
                )
            ),
        )

        return cls(
            auth_token=auth_token,
            docker_image=docker_image,
            temporary_root=(
                temporary_root.resolve()
            ),
            host=host,
            port=port,
            limits=limits,
        )