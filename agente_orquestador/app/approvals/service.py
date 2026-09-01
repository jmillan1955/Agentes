from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.approvals.models import (
    TaskApproval,
)
from app.context.task_approval_repository import (
    TaskApprovalRepository,
)
from app.context.task_execution_repository import (
    TaskExecutionRepository,
)
from app.context.task_plan_repository import (
    TaskPlanRepository,
)
from app.context.task_repository import (
    TaskRepository,
)
from app.planning import (
    PlanStatus,
    TaskPlan,
)
from app.tasks import (
    TaskRecord,
    TaskStatus,
)


class ApprovalError(ValueError):
    """Error al aprobar una tarea."""


class ApprovalPermissionError(
    ApprovalError
):
    """El usuario no puede aprobar tareas."""


class ApprovalValidationError(
    ApprovalError
):
    """La tarea o su plan no son aprobables."""


@dataclass(frozen=True, slots=True)
class ApprovalResult:
    approval: TaskApproval
    task: TaskRecord
    plan: TaskPlan
    already_approved: bool


class ApprovalService:
    def __init__(
        self,
        task_repository: TaskRepository,
        plan_repository: TaskPlanRepository,
        approval_repository: (
            TaskApprovalRepository
        ),
        approver_user_ids: Iterable[
            int | str
        ],
        execution_repository: (
            TaskExecutionRepository | None
        ) = None,
    ) -> None:
        normalized_approvers = tuple(
            dict.fromkeys(
                str(user_id).strip()
                for user_id in approver_user_ids
                if str(user_id).strip()
            )
        )

        if not normalized_approvers:
            raise ValueError(
                "approver_user_ids no puede "
                "estar vacio"
            )

        self._task_repository = (
            task_repository
        )
        self._plan_repository = (
            plan_repository
        )
        self._approval_repository = (
            approval_repository
        )
        self._approver_user_ids = frozenset(
            normalized_approvers
        )

        self._execution_repository = (
            execution_repository
        )

    def ensure_approver(
        self,
        user_id: str,
    ) -> None:
        normalized_user_id = user_id.strip()

        if (
            normalized_user_id
            not in self._approver_user_ids
        ):
            raise ApprovalPermissionError(
                "No tienes permiso para "
                "confirmar promociones"
            )

    def approve(
        self,
        task_id: int,
        authorized_user_id: str,
        authorization_message_id: str,
        channel: str,
    ) -> ApprovalResult:
        if task_id <= 0:
            raise ApprovalValidationError(
                "El identificador de tarea "
                "debe ser mayor que cero"
            )

        authorized_user_id = (
            authorized_user_id.strip()
        )
        authorization_message_id = (
            authorization_message_id.strip()
        )
        channel = channel.strip()

        if (
            authorized_user_id
            not in self._approver_user_ids
        ):
            raise ApprovalPermissionError(
                "No tienes permiso para "
                "aprobar planes"
            )

        if not authorization_message_id:
            raise ApprovalValidationError(
                "El mensaje de autorizacion "
                "no puede estar vacio"
            )

        if not channel:
            raise ApprovalValidationError(
                "El canal no puede estar vacio"
            )

        existing = (
            self._approval_repository
            .get_by_task_id(task_id)
        )

        if existing is not None:
            return self._build_result(
                approval=existing,
                already_approved=True,
            )

        task = self._task_repository.get_by_id(
            task_id
        )

        if task is None:
            raise ApprovalValidationError(
                f"No existe la tarea #{task_id}"
            )

        plan = self._plan_repository.get_latest(
            task_id
        )

        if plan is None:
            raise ApprovalValidationError(
                "La tarea no tiene ningun plan"
            )

        if (
            task.status
            != TaskStatus.PENDING_APPROVAL
        ):
            raise ApprovalValidationError(
                "La tarea no esta pendiente "
                "de aprobacion"
            )

        if (
            plan.status
            != PlanStatus.PENDING_APPROVAL
        ):
            raise ApprovalValidationError(
                "El plan no esta pendiente "
                "de aprobacion"
            )

        if not plan.can_be_approved:
            raise ApprovalValidationError(
                "El plan no contiene toda "
                "la informacion necesaria"
            )

        approval = (
            self._approval_repository.approve(
                task_id=task.id,
                plan_id=plan.id,
                plan_version=plan.version,
                authorized_user_id=(
                    authorized_user_id
                ),
                authorization_message_id=(
                    authorization_message_id
                ),
                channel=channel,
            )
        )

        return self._build_result(
            approval=approval,
            already_approved=False,
        )

    def cancel(
        self,
        task_id: int,
        authorized_user_id: str,
    ) -> CancellationResult:
        if task_id <= 0:
            raise ApprovalValidationError(
                "El identificador de tarea "
                "debe ser mayor que cero"
            )

        authorized_user_id = (
            authorized_user_id.strip()
        )

        if (
            authorized_user_id
            not in self._approver_user_ids
        ):
            raise ApprovalPermissionError(
                "No tienes permiso para "
                "cancelar tareas aprobadas"
            )

        approval = (
            self._approval_repository
            .get_by_task_id(task_id)
        )

        if approval is None:
            raise ApprovalValidationError(
                "La tarea no tiene una aprobacion "
                "que pueda cancelarse"
            )

        task = self._task_repository.get_by_id(
            task_id
        )

        plan = self._plan_repository.get_by_id(
            approval.plan_id
        )

        if task is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la tarea aprobada"
            )

        if plan is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el plan aprobado"
            )

        if task.status == TaskStatus.CANCELLED:
            return CancellationResult(
                approval=approval,
                task=task,
                plan=plan,
                cancelled_user_id=(
                    authorized_user_id
                ),
                already_cancelled=True,
            )

        if task.status != TaskStatus.APPROVED:
            raise ApprovalValidationError(
                "Solamente puede cancelarse una "
                "tarea que este aprobada"
            )

        execution = None

        if self._execution_repository is not None:
            execution = (
                self._execution_repository
                .get_by_task_id(task.id)
            )

        if execution is not None:
            self._execution_repository.cancel(
                execution.id
            )

            cancelled_task = (
                self._task_repository
                .get_by_id(task.id)
            )

            if cancelled_task is None:
                raise RuntimeError(
                    "No se pudo recuperar "
                    "la tarea cancelada"
                )

        else:
            cancelled_task = (
                self._task_repository.cancel(
                    task.id
                )
            )
        return CancellationResult(
            approval=approval,
            task=cancelled_task,
            plan=plan,
            cancelled_user_id=(
                authorized_user_id
            ),
            already_cancelled=False,
        )

    def _build_result(
        self,
        approval: TaskApproval,
        already_approved: bool,
    ) -> ApprovalResult:
        task = self._task_repository.get_by_id(
            approval.task_id
        )

        plan = self._plan_repository.get_by_id(
            approval.plan_id
        )

        if task is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "la tarea aprobada"
            )

        if plan is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el plan aprobado"
            )

        return ApprovalResult(
            approval=approval,
            task=task,
            plan=plan,
            already_approved=already_approved,
        )

@dataclass(frozen=True, slots=True)
class CancellationResult:
    approval: TaskApproval
    task: TaskRecord
    plan: TaskPlan
    cancelled_user_id: str
    already_cancelled: bool