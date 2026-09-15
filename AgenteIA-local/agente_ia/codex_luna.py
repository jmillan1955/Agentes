from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai_codex import AsyncCodex, AsyncThread, CodexConfig, Sandbox


DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT = "none"
MODEL_PRICING_USD = {
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
    "gpt-5.6-sol": (4.00, 0.40, 20.00),
}


def calculate_api_cost_usd(
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Calcula el coste API equivalente cuando conocemos la tarifa del modelo."""
    pricing = MODEL_PRICING_USD.get(model)
    if pricing is None:
        return None
    input_price, cached_input_price, output_price = pricing
    safe_input = max(input_tokens, 0)
    safe_cached = min(max(cached_input_tokens, 0), safe_input)
    uncached_input = safe_input - safe_cached
    return (
        uncached_input * input_price
        + safe_cached * cached_input_price
        + max(output_tokens, 0) * output_price
    ) / 1_000_000


class CodexModelError(RuntimeError):
    """Error controlado al consultar un modelo mediante Codex."""


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    model: str
    reasoning_effort: str
    elapsed_seconds: float
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_output_tokens: int
    account_plan: str

    @property
    def equivalent_api_cost_usd(self) -> float | None:
        return calculate_api_cost_usd(
            self.model,
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
        )


class CodexModelService:
    """Mantiene una conversación Codex independiente por chat de Telegram."""

    def __init__(
        self,
        project_dir: Path,
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        codex_home: Path | None = None,
        codex_factory: Any = AsyncCodex,
    ) -> None:
        self.project_dir = project_dir.resolve()
        self.model = model.strip() or DEFAULT_MODEL
        self.reasoning_effort = reasoning_effort.strip() or DEFAULT_REASONING_EFFORT
        self.codex_home = codex_home.resolve() if codex_home is not None else None
        self._codex_factory = codex_factory
        self._codex: AsyncCodex | None = None
        self._account_plan = "unknown"
        self._threads: dict[int, AsyncThread] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    @property
    def account_plan(self) -> str:
        return self._account_plan

    async def start(self) -> None:
        if self._codex is not None:
            return

        child_env = dict(os.environ)
        if self.codex_home is not None:
            child_env["CODEX_HOME"] = str(self.codex_home)
        codex = self._codex_factory(CodexConfig(env=child_env))
        await codex.__aenter__()
        try:
            account_response = await codex.account()
            account = (
                account_response.account.root
                if account_response.account is not None
                else None
            )
            if getattr(account, "type", None) != "chatgpt":
                raise CodexModelError(
                    "Codex debe estar autenticado mediante ChatGPT."
                )

            plan = getattr(account, "plan_type", "unknown")
            self._account_plan = str(getattr(plan, "value", plan)).lower()

            models = await codex.models(include_hidden=True)
            selected_model = next(
                (model for model in models.data if model.model == self.model),
                None,
            )
            if selected_model is None:
                raise CodexModelError(
                    f"El modelo {self.model} no está disponible para esta cuenta."
                )

            efforts = {
                option.reasoning_effort.value
                for option in selected_model.supported_reasoning_efforts
            }
            # El App Server 0.154.0 acepta `none` para GPT-5.6, pero no siempre
            # lo incluye en supported_reasoning_efforts. Los demás niveles sí
            # se validan contra los metadatos devueltos por la cuenta.
            if self.reasoning_effort != "none" and self.reasoning_effort not in efforts:
                raise CodexModelError(
                    f"{self.model} no admite el esfuerzo {self.reasoning_effort}."
                )
        except Exception:
            await codex.close()
            raise

        self._codex = codex

    async def close(self) -> None:
        codex = self._codex
        self._codex = None
        self._threads.clear()
        self._locks.clear()
        if codex is not None:
            await codex.close()

    async def new_conversation(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            self._threads.pop(chat_id, None)

    async def ask(
        self,
        chat_id: int,
        prompt: str,
        *,
        initial_context: str = "",
    ) -> ModelResponse:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise CodexModelError("La consulta está vacía.")
        if self._codex is None:
            raise CodexModelError("El servicio Codex todavía no está iniciado.")

        async with self._lock_for(chat_id):
            thread = self._threads.get(chat_id)
            created_thread = thread is None
            if thread is None:
                thread = await self._codex.thread_start(
                    cwd=str(self.project_dir),
                    ephemeral=True,
                    model=self.model,
                    sandbox=Sandbox.read_only,
                )
                self._threads[chat_id] = thread

            turn_prompt = clean_prompt
            # Solo se reconstruye el historial al crear un hilo nuevo. Una vez
            # vivo, Codex ya conserva los turnos siguientes.
            if created_thread and initial_context.strip():
                turn_prompt = (
                    "Continúa esta conversación previa respetando su contexto.\n\n"
                    "HISTORIAL PREVIO\n"
                    f"{initial_context.strip()}\n\n"
                    "NUEVO MENSAJE DEL USUARIO\n"
                    f"{clean_prompt}"
                )

            result = await thread.run(
                turn_prompt,
                effort=self.reasoning_effort,
                sandbox=Sandbox.read_only,
            )

        response_text = (result.final_response or "").strip()
        if not response_text:
            raise CodexModelError(f"{self.model} ha devuelto una respuesta vacía.")

        usage = result.usage.last if result.usage is not None else None
        return ModelResponse(
            text=response_text,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            elapsed_seconds=max((result.duration_ms or 0) / 1000, 0.0),
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
            cached_input_tokens=usage.cached_input_tokens if usage is not None else 0,
            reasoning_output_tokens=(
                usage.reasoning_output_tokens if usage is not None else 0
            ),
            account_plan=self._account_plan,
        )

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        lock = self._locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[chat_id] = lock
        return lock
