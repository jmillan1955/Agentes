from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.execution.sandbox import (
    SandboxRunRequest,
    SandboxRunResult,
)
from app.execution.workspace_package import (
    WorkspacePackager,
)


class SandboxGatewayError(
    RuntimeError
):
    """Error de comunicacion con el gateway."""


class HttpSandboxBackend:
    def __init__(
        self,
        gateway_url: str,
        auth_token: str,
        packager: WorkspacePackager,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,    ) -> None:
        gateway_url = (
            gateway_url.strip().rstrip("/")
        )
        auth_token = auth_token.strip()
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser "
                "mayor que cero"
            )
        parsed = urlparse(gateway_url)

        if (
            parsed.scheme not in {
                "http",
                "https",
            }
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "SANDBOX_GATEWAY_URL no "
                "es valida"
            )

        if len(auth_token) < 32:
            raise ValueError(
                "El token del gateway debe "
                "tener al menos 32 caracteres"
            )

        self._gateway_url = gateway_url
        self._auth_token = auth_token
        self._packager = packager
        self._client = (
            client
            or httpx.Client(
                timeout=timeout_seconds
            )
        )
    def run_pytest(
        self,
        request: SandboxRunRequest,
    ) -> SandboxRunResult:
        files = self._packager.package(
            request.workspace_path
        )

        payload = {
            "files": [
                {
                    "relative_path": (
                        file.relative_path
                    ),
                    "content_base64": (
                        file.content_base64
                    ),
                }
                for file in files
            ],
            "test_target": (
                request.test_target
            ),
            "timeout_seconds": (
                request.timeout_seconds
            ),
            "max_output_characters": (
                request
                .max_output_characters
            ),
        }

        try:
            response = self._client.post(
                (
                    f"{self._gateway_url}"
                    "/v1/pytest"
                ),
                json=payload,
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{self._auth_token}"
                    )
                },
                timeout=(
                    request.timeout_seconds
                    + 10
                ),
            )

        except httpx.TimeoutException as error:
            raise SandboxGatewayError(
                "Tiempo agotado al comunicar "
                "con el gateway"
            ) from error

        except httpx.HTTPError as error:
            raise SandboxGatewayError(
                "No se pudo comunicar con "
                "el gateway"
            ) from error

        if response.status_code != 200:
            raise SandboxGatewayError(
                "El gateway rechazo el trabajo "
                f"con estado "
                f"{response.status_code}"
            )

        try:
            data = response.json()

            return SandboxRunResult(
                exit_code=data["exit_code"],
                stdout_text=data["stdout_text"],
                stderr_text=data["stderr_text"],
                timed_out=data["timed_out"],
                duration_seconds=(
                    data["duration_seconds"]
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise SandboxGatewayError(
                "El gateway devolvio una "
                "respuesta no valida"
            ) from error