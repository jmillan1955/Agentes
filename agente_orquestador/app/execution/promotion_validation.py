from __future__ import annotations

from dataclasses import dataclass
from pathlib import (
    Path,
    PurePosixPath,
)

from app.execution.limits import (
    ExecutionLimits,
)
from app.execution.promotion_paths import (
    PromotionPathError,
    normalize_target_subdirectory,
)
from app.execution.promotion_workflow import (
    PromotionWorkflowError,
    PromotionWorkflowResult,
    PromotionWorkflowService,
)
from app.execution.sandbox import (
    SandboxBackend,
    SandboxRunRequest,
    SandboxRunResult,
)


class PromotionValidationError(
    RuntimeError
):
    """La promocion no supero la validacion."""

    def __init__(
        self,
        message: str,
        sandbox_result: (
            SandboxRunResult | None
        ) = None,
    ) -> None:
        super().__init__(message)

        self.sandbox_result = sandbox_result


@dataclass(frozen=True, slots=True)
class PromotionValidationResult:
    workflow_result: PromotionWorkflowResult
    sandbox_result: SandboxRunResult
    test_target: str


class PromotionValidationService:
    def __init__(
        self,
        workflow_service: (
            PromotionWorkflowService
        ),
        sandbox_backend: SandboxBackend,
        limits: ExecutionLimits,
    ) -> None:
        self._workflow_service = (
            workflow_service
        )
        self._sandbox_backend = (
            sandbox_backend
        )
        self._limits = limits

    def validate(
        self,
        workflow_result: (
            PromotionWorkflowResult
        ),
        test_target: str = ".",
        target_subdirectory: str = ".",
    ) -> PromotionValidationResult:
        try:
            validation_workspace = (
                self._resolve_validation_workspace(
                    repository_root=(
                        workflow_result
                        .branch
                        .repository_root
                    ),
                    target_subdirectory=(
                        target_subdirectory
                    ),
                )
            )

            request = SandboxRunRequest(
                workspace_path=(
                    validation_workspace
                ),
                test_target=test_target,
                timeout_seconds=(
                    self._limits
                    .command_timeout_seconds
                ),
                max_output_characters=(
                    self._limits
                    .max_output_characters
                ),
            )

        except (
            PromotionPathError,
            ValueError,
        ) as error:
            self._rollback_after_failure(
                workflow_result=workflow_result,
                original_error=error,
                sandbox_result=None,
            )

            raise PromotionValidationError(
                "La configuracion de las pruebas "
                f"no es valida: {error}"
            ) from error

        try:
            sandbox_result = (
                self._sandbox_backend
                .run_pytest(request)
            )

        except RuntimeError as error:
            self._rollback_after_failure(
                workflow_result=workflow_result,
                original_error=error,
                sandbox_result=None,
            )

            raise PromotionValidationError(
                "No se pudo ejecutar la "
                "validacion en el sandbox: "
                f"{error}"
            ) from error

        if sandbox_result.timed_out:
            self._rollback_after_failure(
                workflow_result=workflow_result,
                original_error=None,
                sandbox_result=sandbox_result,
            )

            raise PromotionValidationError(
                "Las pruebas de la promocion "
                "agotaron el tiempo permitido",
                sandbox_result=sandbox_result,
            )

        if sandbox_result.exit_code != 0:
            self._rollback_after_failure(
                workflow_result=workflow_result,
                original_error=None,
                sandbox_result=sandbox_result,
            )

            raise PromotionValidationError(
                "Las pruebas de la promocion "
                "finalizaron con errores",
                sandbox_result=sandbox_result,
            )

        return PromotionValidationResult(
            workflow_result=workflow_result,
            sandbox_result=sandbox_result,
            test_target=request.test_target,
        )

    @staticmethod
    def _resolve_validation_workspace(
        repository_root: Path,
        target_subdirectory: str,
    ) -> Path:
        root_input = (
            repository_root.expanduser()
        )

        if root_input.is_symlink():
            raise PromotionPathError(
                "El repositorio no puede ser un "
                "enlace simbolico"
            )

        root = root_input.resolve()

        if not root.is_dir():
            raise PromotionPathError(
                "El repositorio no existe"
            )

        normalized_subdirectory = (
            normalize_target_subdirectory(
                target_subdirectory
            )
        )

        if normalized_subdirectory == ".":
            return root

        relative = PurePosixPath(
            normalized_subdirectory
        )
        candidate = root.joinpath(
            *relative.parts
        )

        current = candidate

        while current != root:
            if current.is_symlink():
                raise PromotionPathError(
                    "El subdirectorio contiene "
                    "un enlace simbolico"
                )

            current = current.parent

        resolved = candidate.resolve()

        if not resolved.is_relative_to(root):
            raise PromotionPathError(
                "El subdirectorio sale del "
                "repositorio"
            )

        if not resolved.is_dir():
            raise PromotionPathError(
                "El subdirectorio objetivo no "
                "existe"
            )

        return resolved

    def _rollback_after_failure(
        self,
        workflow_result: (
            PromotionWorkflowResult
        ),
        original_error: Exception | None,
        sandbox_result: (
            SandboxRunResult | None
        ),
    ) -> None:
        try:
            self._workflow_service.rollback(
                workflow_result
            )

        except PromotionWorkflowError as rollback_error:
            message = (
                "La validacion de la promocion "
                "fallo y no se pudo completar "
                "el rollback: "
                f"{rollback_error}"
            )

            if original_error is not None:
                message = (
                    f"{message}. Error original: "
                    f"{original_error}"
                )

            raise PromotionValidationError(
                message,
                sandbox_result=sandbox_result,
            ) from rollback_error