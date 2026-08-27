from __future__ import annotations

import secrets

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    status,
)
from pydantic import BaseModel

from sandbox_gateway.models import (
    PytestJobRequest,
    SandboxFilePayload,
)
from sandbox_gateway.service import (
    SandboxGatewayService,
)


class FilePayloadModel(BaseModel):
    relative_path: str
    content_base64: str


class PytestJobRequestModel(BaseModel):
    files: list[FilePayloadModel]
    test_target: str
    timeout_seconds: float
    max_output_characters: int


class PytestJobResultModel(BaseModel):
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    timed_out: bool
    duration_seconds: float


def create_app(
    service: SandboxGatewayService,
    auth_token: str,
) -> FastAPI:
    auth_token = auth_token.strip()

    if len(auth_token) < 32:
        raise ValueError(
            "El token del gateway debe tener "
            "al menos 32 caracteres"
        )

    app = FastAPI(
        title="Orchestrator Sandbox Gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def require_authorization(
        authorization: str = Header(
            default=""
        ),
    ) -> None:
        expected = f"Bearer {auth_token}"

        if not secrets.compare_digest(
            authorization,
            expected,
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail="No autorizado",
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/pytest",
        response_model=PytestJobResultModel,
    )
    def run_pytest(
        payload: PytestJobRequestModel,
        authorization_check: None = Depends(
            require_authorization
        ),
    ) -> PytestJobResultModel:
        del authorization_check

        try:
            request = PytestJobRequest(
                files=tuple(
                    SandboxFilePayload(
                        relative_path=(
                            file.relative_path
                        ),
                        content_base64=(
                            file.content_base64
                        ),
                    )
                    for file in payload.files
                ),
                test_target=(
                    payload.test_target
                ),
                timeout_seconds=(
                    payload.timeout_seconds
                ),
                max_output_characters=(
                    payload
                    .max_output_characters
                ),
            )

            result = service.run_pytest(
                request
            )

        except ValueError as error:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=str(error),
            ) from error

        return PytestJobResultModel(
            exit_code=result.exit_code,
            stdout_text=result.stdout_text,
            stderr_text=result.stderr_text,
            timed_out=result.timed_out,
            duration_seconds=(
                result.duration_seconds
            ),
        )

    return app