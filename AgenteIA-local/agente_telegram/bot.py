from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agente_ia import (
    CalendarDraftError,
    CalendarEventDraft,
    CalendarServiceError,
    CodexModelError,
    CodexModelService,
    Conversation,
    ConversationStore,
    HikingMapService,
    HomeAssistantCalendarService,
    MapResult,
    MapServiceError,
    ModelResponse,
    format_calendar_draft,
    format_calendar_events,
    parse_calendar_event_draft,
    parse_calendar_query,
)
from agente_telegram.transcription_service import TranscriptionService


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODEL_ALIASES = {
    "luna": "gpt-5.6-luna",
    "terra": "gpt-5.6-terra",
    "sol": "gpt-5.6-sol",
}


def parse_model_selection(text: str) -> str:
    raw = text.strip().lower()
    if "=" in raw:
        return raw.split("=", 1)[1].strip().removeprefix("gpt-5.6-")
    parts = raw.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip().removeprefix("gpt-5.6-")
    return ""

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_token: str
    allowed_user_ids: tuple[int, ...]
    whisper_model: str
    codex_model: str
    codex_reasoning_effort: str
    codex_home_free: Path
    codex_home_plus: Path
    conversation_database_path: Path
    home_assistant_url: str
    home_assistant_token: str
    family_calendar_entity_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_DIR / ".env")
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        user_ids = (
            os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
            or os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        )
        if not token:
            raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en .env")
        if not user_ids:
            raise RuntimeError("Falta TELEGRAM_ALLOWED_USER_IDS en .env")
        try:
            parsed_user_ids = tuple(
                dict.fromkeys(
                    int(value.strip())
                    for value in user_ids.split(",")
                    if value.strip()
                )
            )
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_IDS debe contener números separados por comas"
            ) from exc
        if not parsed_user_ids:
            raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS está vacío")
        codex_home_free = Path(
            os.getenv(
                "AGENTEIA_CODEX_HOME_FREE",
                os.getenv(
                    "AGENTEIA_CODEX_HOME",
                    str(Path.home() / ".codex-agenteia-free"),
                ),
            ).strip()
        ).expanduser()
        codex_home_plus = Path(
            os.getenv(
                "AGENTEIA_CODEX_HOME_PLUS",
                str(Path.home() / ".codex"),
            ).strip()
        ).expanduser()
        for profile_name, profile_path in (
            ("Free", codex_home_free),
            ("Plus", codex_home_plus),
        ):
            if not profile_path.is_dir():
                raise RuntimeError(
                    f"El perfil Codex {profile_name} no existe: {profile_path}"
                )
        return cls(
            telegram_token=token,
            allowed_user_ids=parsed_user_ids,
            whisper_model=os.getenv("WHISPER_MODEL", "small").strip() or "small",
            codex_model=(
                os.getenv("CODEX_MODEL", "gpt-5.6-terra").strip()
                or "gpt-5.6-terra"
            ),
            codex_reasoning_effort=(
                os.getenv("CODEX_REASONING_EFFORT", "none").strip() or "none"
            ),
            codex_home_free=codex_home_free,
            codex_home_plus=codex_home_plus,
            conversation_database_path=(
                Path(
                    os.getenv(
                        "CONVERSATION_DATABASE_PATH",
                        "data/conversations.db",
                    ).strip()
                    or "data/conversations.db"
                ).expanduser()
            ),
            home_assistant_url=os.getenv("HOME_ASSISTANT_URL", "").strip(),
            home_assistant_token=os.getenv("HOME_ASSISTANT_TOKEN", "").strip(),
            family_calendar_entity_id=os.getenv(
                "HOME_ASSISTANT_FAMILY_CALENDAR_ENTITY_ID", ""
            ).strip(),
        )


class TelegramAgent:
    def __init__(
        self,
        settings: Settings,
        model_services: dict[str, CodexModelService],
        default_model_key: str,
        transcription: TranscriptionService,
        map_service: HikingMapService,
        calendar_service: HomeAssistantCalendarService,
        conversation_store: ConversationStore,
    ) -> None:
        self.settings = settings
        self.model_services = model_services
        self.default_model_key = default_model_key
        self.transcription = transcription
        self.map_service = map_service
        self.calendar_service = calendar_service
        self.conversation_store = conversation_store

    async def start_service(self, application: Application) -> None:
        del application
        self.conversation_store.initialize()
        for key, service in self.model_services.items():
            await service.start()
            logger.info(
                "Modelo %s conectado: %s, razonamiento %s, plan %s",
                key,
                service.model,
                service.reasoning_effort,
                service.account_plan,
            )

    async def stop_service(self, application: Application) -> None:
        del application
        await asyncio.gather(
            *(service.close() for service in self.model_services.values())
        )

    def register_handlers(self, application: Application) -> None:
        application.add_handler(
            MessageHandler(filters.ALL, self.confirmar_recepcion), group=-1
        )
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("mi_id", self.mostrar_id))
        application.add_handler(CommandHandler("debug", self.cambiar_debug))
        application.add_handler(CommandHandler("nuevo", self.nueva_conversacion))
        application.add_handler(
            CommandHandler("conversaciones", self.listar_conversaciones)
        )
        application.add_handler(CommandHandler("abrir", self.abrir_conversacion))
        application.add_handler(CommandHandler("historial", self.mostrar_historial))
        application.add_handler(CommandHandler("agenda", self.consultar_agenda))
        application.add_handler(CommandHandler("evento", self.crear_evento_command))
        application.add_handler(
            CallbackQueryHandler(
                self.resolver_evento_calendario,
                pattern=r"^calendar:(?:confirm|cancel)$",
            )
        )
        application.add_handler(
            MessageHandler(
                filters.TEXT & filters.Regex(r"^/modelo(?:=|\s|$)"),
                self.cambiar_modelo,
            )
        )
        application.add_handler(
            CommandHandler("confirmar_audio", self.confirmar_audio)
        )
        for command in ("corregido", "corregir_audio", "revisar"):
            application.add_handler(CommandHandler(command, self.corregir_audio))
        application.add_handler(
            MessageHandler(filters.COMMAND, self.responder_texto)
        )
        application.add_handler(MessageHandler(filters.VOICE, self.recibir_voz))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.responder_texto)
        )

    def usuario_autorizado(self, update: Update) -> bool:
        user = update.effective_user
        authorized = (
            user is not None and user.id in self.settings.allowed_user_ids
        )
        if user is not None and not authorized:
            logger.warning("Acceso de Telegram rechazado para %s", user.id)
        return authorized

    def conversacion_activa(self, update: Update) -> Conversation:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None:
            raise RuntimeError("Telegram no ha proporcionado usuario o conversación.")
        database_user_id = self.usuario_base_datos(update)
        return self.conversation_store.get_or_create_active_conversation(
            database_user_id, chat.id
        )

    def usuario_base_datos(self, update: Update) -> int:
        user = update.effective_user
        if user is None:
            raise RuntimeError("Telegram no ha proporcionado usuario.")
        return self.conversation_store.get_or_create_user(
            user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    @staticmethod
    def debug_activo(context: ContextTypes.DEFAULT_TYPE) -> bool:
        return bool(context.user_data.get("debug", False))

    def modelo_activo(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        key = context.chat_data.get("model_key", self.default_model_key)
        return key if key in self.model_services else self.default_model_key

    def servicio_activo(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> CodexModelService:
        return self.model_services[self.modelo_activo(context)]

    async def responder_telegram(
        self,
        update: Update,
        text: str,
        *,
        response: ModelResponse | None = None,
        elapsed_seconds: float = 0.0,
        model: str = "No aplica",
        provider: str = "interno",
        zero_token_operation: bool = False,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        if update.message is None:
            return

        if response is not None:
            elapsed_seconds = response.elapsed_seconds
            model = response.model
            provider = "Codex / ChatGPT"
            tokens = f"{response.input_tokens} entrada"
            if response.cached_input_tokens:
                tokens += f" ({response.cached_input_tokens} en caché)"
            tokens += f" + {response.output_tokens} salida"
            if response.reasoning_output_tokens:
                tokens += f" ({response.reasoning_output_tokens} razonamiento)"
            equivalent_cost = response.equivalent_api_cost_usd
            if equivalent_cost is None:
                api_cost = "Tarifa no configurada"
            else:
                api_cost = (
                    f"US${equivalent_cost:.6f}".replace(".", ",")
                    + f" (equivalente API; plan {response.account_plan})"
                )
            effort = response.reasoning_effort
            account_plan = response.account_plan
        else:
            tokens = "0 entrada + 0 salida" if zero_token_operation else "No aplica"
            api_cost = "US$0,000000" if zero_token_operation else "No aplica"
            effort = "No aplica"
            account_plan = "No aplica"

        minutes = f"{max(elapsed_seconds, 0.0) / 60:.2f}".replace(".", ",")
        footer = "\n".join(
            [
                f"⏱️ Tiempo de ejecución: {minutes} minutos",
                f"🤖 Modelo: {model}",
                f"🧠 Razonamiento: {effort}",
                f"🔌 Proveedor: {provider}",
                f"👤 Plan ChatGPT: {account_plan}",
                f"🔢 Tokens: {tokens}",
                f"💵 Coste de tokens: {api_cost}",
            ]
        )
        max_length = 4096 - len(footer) - 2
        remaining = text.strip() or "Respuesta vacía"
        while remaining:
            if len(remaining) <= max_length:
                fragment, remaining = remaining, ""
            else:
                split_at = remaining.rfind("\n", 0, max_length)
                if split_at < max_length // 2:
                    split_at = remaining.rfind(" ", 0, max_length)
                if split_at <= 0:
                    split_at = max_length
                fragment = remaining[:split_at].rstrip()
                remaining = remaining[split_at:].lstrip()
            await update.message.reply_text(
                f"{fragment}\n\n{footer}",
                reply_markup=reply_markup if not remaining else None,
            )

    async def responder_debug(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
    ) -> None:
        if self.debug_activo(context):
            await self.responder_telegram(update, f"🔎 DEBUG\n\n{text}")

    async def confirmar_recepcion(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if self.usuario_autorizado(update) and update.message is not None:
            await update.message.reply_text("✅ Entrada recibida. Inicio el procesamiento.")

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        service = self.servicio_activo(context)
        await self.responder_telegram(
            update,
            "Hola, José.\n\n"
            "AgenteIA-local está conectado mediante Telegram a "
            f"{service.model}.\n"
            "Puedes enviar texto o una nota de voz.\n\n"
            "Comandos:\n"
            "/nuevo [nombre] - crea y nombra una conversación\n"
            "/conversaciones - muestra tus últimas conversaciones\n"
            "/abrir <id> - continúa una conversación anterior\n"
            "/historial - muestra los últimos mensajes\n"
            "/agenda [días] - consulta el calendario familiar\n"
            "/evento <datos> - prepara un evento para confirmarlo\n"
            "/modelo=sol|terra|luna - cambia de modelo\n"
            "/debug - muestra u oculta mensajes intermedios\n"
            "/mi_id - muestra tu identificador de Telegram\n"
            "/confirmar_audio - acepta la última transcripción\n"
            "/corregido <texto> - corrige y procesa la transcripción",
        )

    async def cambiar_modelo(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if (
            not self.usuario_autorizado(update)
            or update.message is None
            or update.message.text is None
            or update.effective_chat is None
        ):
            return

        requested = parse_model_selection(update.message.text)

        if not requested:
            active = self.modelo_activo(context)
            await self.responder_telegram(
                update,
                f"Modelo activo: {active}.\n\n"
                "Opciones: /modelo=sol, /modelo=terra o /modelo=luna.",
            )
            return

        if requested not in self.model_services:
            await self.responder_telegram(
                update,
                "Modelo no válido. Usa /modelo=sol, /modelo=terra "
                "o /modelo=luna.",
            )
            return

        service = self.model_services[requested]
        conversation = self.conversacion_activa(update)
        await asyncio.gather(
            *(item.new_conversation(conversation.id) for item in self.model_services.values())
        )
        context.chat_data["model_key"] = requested
        await self.responder_telegram(
            update,
            f"Modelo cambiado a {service.model}.\n"
            f"Razonamiento: {service.reasoning_effort}.\n"
            "Se ha iniciado una conversación nueva para este modelo.",
        )

    async def mostrar_id(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if not self.usuario_autorizado(update) or update.effective_user is None:
            return
        await self.responder_telegram(
            update,
            f"Tu identificador de Telegram es:\n\n{update.effective_user.id}",
        )

    async def cambiar_debug(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        argument = " ".join(context.args or []).strip().lower()
        if argument in {"on", "activar", "activo", "1", "si", "sí"}:
            enabled = True
        elif argument in {"off", "desactivar", "inactivo", "0", "no"}:
            enabled = False
        elif not argument:
            enabled = not self.debug_activo(context)
        else:
            await self.responder_telegram(update, "Uso: /debug, /debug on o /debug off")
            return
        context.user_data["debug"] = enabled
        await self.responder_telegram(
            update,
            "Debug activado. Se mostrarán los pasos intermedios."
            if enabled
            else "Debug desactivado. Solo se mostrará el resultado final.",
        )

    async def nueva_conversacion(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if (
            not self.usuario_autorizado(update)
            or update.message is None
            or update.effective_chat is None
        ):
            return
        requested_title = " ".join(context.args or []).strip()
        if not requested_title:
            context.user_data["awaiting_conversation_name"] = True
            await self.responder_telegram(
                update,
                "Escribe ahora el nombre de la nueva conversación "
                "(máximo 70 caracteres).",
            )
            return
        await self.crear_conversacion(update, context, requested_title)

    async def crear_conversacion(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        title: str,
    ) -> bool:
        if update.effective_chat is None:
            return False
        clean_title = " ".join(title.split()).strip()
        if not clean_title or len(clean_title) > 70:
            await self.responder_telegram(
                update,
                "El nombre debe tener entre 1 y 70 caracteres. Escribe otro nombre.",
            )
            return False
        database_user_id = self.usuario_base_datos(update)
        current = self.conversation_store.get_active_conversation(
            database_user_id, update.effective_chat.id
        )
        new_conversation = self.conversation_store.start_new_conversation(
            database_user_id,
            update.effective_chat.id,
            title=clean_title,
        )
        if current is not None:
            await asyncio.gather(
                *(item.new_conversation(current.id) for item in self.model_services.values())
            )
        await self.responder_telegram(
            update,
            f"Conversación creada: «{new_conversation.title}» "
            f"(identificador {new_conversation.id}).\n\n"
            "Ya puedes enviar la primera pregunta.",
        )
        context.user_data.pop("awaiting_conversation_name", None)
        return True

    async def listar_conversaciones(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if not self.usuario_autorizado(update) or update.message is None:
            return
        active = self.conversacion_activa(update)
        conversations = self.conversation_store.list_conversations(active.user_id)
        lines = ["Tus conversaciones:"]
        for conversation in conversations:
            marker = "●" if conversation.status == "active" else "○"
            lines.append(f"{marker} {conversation.id}: {conversation.title}")
        lines.append("\nUsa /abrir <id> para continuar una conversación.")
        await self.responder_telegram(update, "\n".join(lines))

    async def abrir_conversacion(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if (
            not self.usuario_autorizado(update)
            or update.message is None
            or update.effective_chat is None
        ):
            return
        argument = " ".join(context.args or []).strip()
        if not argument.isdigit():
            await self.responder_telegram(update, "Uso: /abrir <id>")
            return
        current = self.conversacion_activa(update)
        selected = self.conversation_store.activate_conversation(
            current.user_id, update.effective_chat.id, int(argument)
        )
        if selected is None:
            await self.responder_telegram(
                update, "No existe esa conversación entre tus conversaciones."
            )
            return
        await asyncio.gather(
            *(item.new_conversation(current.id) for item in self.model_services.values()),
            *(item.new_conversation(selected.id) for item in self.model_services.values()),
        )
        await self.responder_telegram(
            update,
            f"Conversación {selected.id} abierta: {selected.title}",
        )

    async def mostrar_historial(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if not self.usuario_autorizado(update) or update.message is None:
            return
        conversation = self.conversacion_activa(update)
        messages = self.conversation_store.recent_messages(conversation.id, limit=10)
        if not messages:
            await self.responder_telegram(update, "Esta conversación todavía está vacía.")
            return
        lines = [f"Historial de «{conversation.title}»:"]
        for message in messages:
            speaker = "Tú" if message.direction == "incoming" else "Agente"
            text = (message.text or "").replace("\n", " ").strip()
            lines.append(f"\n{speaker}: {text[:350]}")
        await self.responder_telegram(update, "\n".join(lines))

    async def responder_texto(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return
        if update.message is None or update.message.text is None:
            return
        if context.user_data.get("awaiting_conversation_name"):
            await self.crear_conversacion(
                update,
                context,
                update.message.text,
            )
            return
        if update.message.text.strip().lower().startswith("\\corregido"):
            await self.corregir_audio(update, context)
            return
        await self.procesar_prompt(update, context, update.message.text)

    async def consultar_agenda(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        argument = " ".join(context.args or []).strip()
        prompt = f"agenda {argument}".strip()
        await self.procesar_prompt(
            update,
            context,
            prompt,
            progress_text="Consultando el calendario familiar...",
            content_type="calendar_query",
        )

    async def crear_evento_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        argument = " ".join(context.args or []).strip()
        if not argument:
            await self.responder_telegram(
                update,
                "Uso: /evento Dentista mañana a las 18:00 durante 45 minutos",
            )
            return
        await self.procesar_prompt(
            update,
            context,
            f"Añade al calendario familiar {argument}",
            progress_text="Preparando el evento...",
            content_type="calendar_create_request",
        )

    async def resolver_evento_calendario(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        callback = update.callback_query
        if callback is None:
            return
        if not self.usuario_autorizado(update):
            await callback.answer("Usuario no autorizado.", show_alert=True)
            return
        await callback.answer()
        draft = context.user_data.get("pending_calendar_event")
        if not isinstance(draft, CalendarEventDraft):
            await callback.edit_message_text(
                "Este borrador ha caducado. Envía de nuevo los datos del evento."
            )
            return

        if callback.data == "calendar:cancel":
            context.user_data.pop("pending_calendar_event", None)
            await callback.edit_message_text(
                "❌ Evento cancelado. No se ha modificado el calendario.\n\n"
                + self.pie_operacion_sin_tokens("interno")
            )
            return

        started_at = perf_counter()
        try:
            await self.calendar_service.create_event(draft)
        except CalendarServiceError as exc:
            logger.warning("No se pudo crear el evento: %s", type(exc).__name__)
            await callback.edit_message_text(
                f"No se ha podido crear el evento.\n\n{exc}\n\n"
                + self.pie_operacion_sin_tokens("Home Assistant + Google Calendar")
            )
            return

        context.user_data.pop("pending_calendar_event", None)
        text = (
            f"✅ Evento creado en Familia Millan Romero.\n\n"
            f"📌 {draft.summary}\n"
            f"📅 {draft.start:%d/%m/%Y}\n"
            f"🕒 {draft.start:%H:%M}–{draft.end:%H:%M}"
        )
        if draft.location:
            text += f"\n📍 {draft.location}"
        text += "\n\nPuede tardar unos segundos en aparecer en el calendario."
        text += "\n\n" + self.pie_operacion_sin_tokens(
            "Home Assistant + Google Calendar",
            elapsed_seconds=perf_counter() - started_at,
        )
        await callback.edit_message_text(text)
        if update.effective_chat is not None:
            conversation = self.conversacion_activa(update)
            self.conversation_store.save_message(
                conversation.id,
                update.effective_chat.id,
                telegram_message_id=None,
                direction="outgoing",
                content_type="calendar_created",
                text=text.split("\n\n⏱️", 1)[0],
            )

    @staticmethod
    def pie_operacion_sin_tokens(
        provider: str, *, elapsed_seconds: float = 0.0
    ) -> str:
        minutes = f"{max(elapsed_seconds, 0.0) / 60:.2f}".replace(".", ",")
        return "\n".join(
            [
                f"⏱️ Tiempo de ejecución: {minutes} minutos",
                "🤖 Modelo: No aplica",
                "🧠 Razonamiento: No aplica",
                f"🔌 Proveedor: {provider}",
                "👤 Plan ChatGPT: No aplica",
                "🔢 Tokens: 0 entrada + 0 salida",
                "💵 Coste de tokens: US$0,000000",
            ]
        )

    async def procesar_prompt(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        prompt: str,
        progress_text: str = "Enviando la petición al modelo...",
        content_type: str = "text",
    ) -> bool:
        if update.message is None or update.effective_chat is None:
            return False
        await self.responder_debug(update, context, progress_text)
        conversation = self.conversacion_activa(update)
        previous_context = self.conversation_store.context_text(conversation.id)
        saved = self.conversation_store.save_message(
            conversation.id,
            update.effective_chat.id,
            telegram_message_id=update.message.message_id,
            direction="incoming",
            content_type=content_type,
            text=prompt,
        )
        if not saved:
            logger.info("Mensaje duplicado de Telegram ignorado: %s", update.message.message_id)
            return False
        try:
            calendar_draft = parse_calendar_event_draft(prompt)
        except CalendarDraftError as exc:
            await self.responder_telegram(
                update,
                str(exc),
                provider="interno",
                zero_token_operation=True,
            )
            return False
        if calendar_draft is not None:
            context.user_data["pending_calendar_event"] = calendar_draft
            preview = format_calendar_draft(calendar_draft)
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "✅ Confirmar", callback_data="calendar:confirm"
                    ),
                    InlineKeyboardButton(
                        "❌ Cancelar", callback_data="calendar:cancel"
                    ),
                ]]
            )
            self.conversation_store.save_message(
                conversation.id,
                update.effective_chat.id,
                telegram_message_id=None,
                direction="outgoing",
                content_type="calendar_preview",
                text=preview,
            )
            await self.responder_telegram(
                update,
                preview,
                provider="interno",
                zero_token_operation=True,
                reply_markup=keyboard,
            )
            return True

        calendar_query = parse_calendar_query(prompt)
        if calendar_query is not None:
            await self.responder_debug(
                update,
                context,
                "Consultando Familia Millan Romero en Home Assistant...",
            )
            try:
                events = await self.calendar_service.events(calendar_query)
                text = format_calendar_events(events, calendar_query.label)
            except CalendarServiceError as exc:
                logger.warning("No se pudo consultar el calendario: %s", type(exc).__name__)
                await self.responder_telegram(
                    update,
                    str(exc),
                    provider="Home Assistant + Google Calendar",
                )
                return False
            self.conversation_store.save_message(
                conversation.id,
                update.effective_chat.id,
                telegram_message_id=None,
                direction="outgoing",
                content_type="calendar",
                text=text,
            )
            await self.responder_telegram(
                update,
                text,
                provider="Home Assistant + Google Calendar",
                zero_token_operation=True,
            )
            await asyncio.gather(
                *(item.new_conversation(conversation.id) for item in self.model_services.values())
            )
            return True
        if self.map_service.supports(prompt):
            await self.responder_debug(
                update,
                context,
                "Calculando las rutas y dibujando el mapa...",
            )
            try:
                map_result = await self.map_service.create(prompt)
                self.conversation_store.save_message(
                    conversation.id,
                    update.effective_chat.id,
                    telegram_message_id=None,
                    direction="outgoing",
                    content_type="map",
                    text=map_result.caption,
                )
                await self.responder_mapa(update, map_result)
                await asyncio.gather(
                    *(item.new_conversation(conversation.id) for item in self.model_services.values())
                )
                return True
            except (MapServiceError, httpx.HTTPError, OSError) as exc:
                logger.warning("No se pudo crear el mapa: %s", type(exc).__name__)
                await self.responder_telegram(
                    update,
                    "No se ha podido generar el mapa cartográfico. Inténtalo de nuevo más tarde.",
                    provider="OpenStreetMap + BRouter",
                )
                return False
        try:
            service = self.servicio_activo(context)
            response = await service.ask(
                conversation.id,
                prompt,
                initial_context=previous_context,
            )
        except (CodexModelError, RuntimeError) as exc:
            logger.warning("El modelo no pudo responder: %s", type(exc).__name__)
            await self.responder_telegram(
                update,
                "No se ha podido obtener una respuesta del modelo.\n\n"
                f"{exc}",
                model=service.model,
                provider="Codex / ChatGPT",
            )
            return False
        self.conversation_store.save_message(
            conversation.id,
            update.effective_chat.id,
            telegram_message_id=None,
            direction="outgoing",
            content_type="text",
            text=response.text,
            model=response.model,
            reasoning_effort=response.reasoning_effort,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        await self.responder_telegram(update, response.text, response=response)
        return True

    async def responder_mapa(self, update: Update, result: MapResult) -> None:
        if update.message is None:
            return
        minutes = f"{result.elapsed_seconds / 60:.2f}".replace(".", ",")
        footer = "\n".join(
            [
                f"⏱️ Tiempo de ejecución: {minutes} minutos",
                "🤖 Modelo: No aplica",
                "🧠 Razonamiento: No aplica",
                "🔌 Proveedor: OpenStreetMap + BRouter",
                "👤 Plan ChatGPT: No aplica",
                "🔢 Tokens: 0 entrada + 0 salida",
                "💵 Coste de tokens: US$0,000000",
            ]
        )
        try:
            with result.image_path.open("rb") as image_file:
                await update.message.reply_photo(
                    photo=image_file,
                    caption=f"{result.caption}\n\n{footer}",
                )
        finally:
            result.image_path.unlink(missing_ok=True)

    async def recibir_voz(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update):
            return
        if update.message is None or update.message.voice is None:
            return

        started_at = perf_counter()
        voice = update.message.voice
        temp_dir = Path(tempfile.gettempdir()) / "agente_telegram"
        temp_dir.mkdir(parents=True, exist_ok=True)
        audio_path = temp_dir / f"{voice.file_unique_id}.ogg"
        try:
            await self.responder_debug(
                update, context, "Nota de voz recibida. Descargando el audio..."
            )
            telegram_file = await context.bot.get_file(voice.file_id)
            await telegram_file.download_to_drive(custom_path=audio_path)
            await self.responder_debug(update, context, "Transcribiendo el audio...")
            text = await asyncio.to_thread(self.transcription.transcribe, audio_path)
            if not text:
                await self.responder_telegram(
                    update, "No he podido reconocer texto en la nota de voz."
                )
                return

            context.user_data["pending_audio"] = {"text": text}
            editable_command = f"/corregido {text}"
            keyboard = None
            if len(editable_command) <= 256:
                keyboard = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton(
                            "📋 Copiar para revisar",
                            copy_text=CopyTextButton(text=editable_command),
                        )
                    ]]
                )
            await self.responder_telegram(
                update,
                "Transcripción:\n\n"
                f"{editable_command}\n\n"
                "Cópiala, corrígela si hace falta y envíala. "
                "También puedes usar /confirmar_audio.",
                elapsed_seconds=perf_counter() - started_at,
                model=self.transcription.model_name,
                provider="faster-whisper",
                zero_token_operation=True,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.error("No se pudo procesar el audio: %s", type(exc).__name__)
            await self.responder_telegram(
                update, "No se ha podido procesar la nota de voz."
            )
        finally:
            audio_path.unlink(missing_ok=True)

    async def corregir_audio(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        pending = context.user_data.get("pending_audio")
        if not isinstance(pending, dict):
            await self.responder_telegram(
                update, "No hay ninguna transcripción de audio pendiente."
            )
            return
        corrected = " ".join(context.args or []).strip()
        if not corrected and update.message.text:
            raw = update.message.text.strip()
            if raw.lower().startswith("\\corregido"):
                corrected = raw[len("\\corregido") :].strip()
        if not corrected:
            await self.responder_telegram(update, "Uso: /corregido <texto validado>")
            return
        completed = await self.procesar_prompt(
            update,
            context,
            corrected,
            progress_text="Transcripción corregida. Enviando al modelo...",
            content_type="audio_transcription",
        )
        if completed:
            context.user_data.pop("pending_audio", None)

    async def confirmar_audio(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        pending = context.user_data.get("pending_audio")
        if not isinstance(pending, dict):
            await self.responder_telegram(
                update, "No hay ninguna transcripción de audio pendiente."
            )
            return
        text = pending.get("text")
        if not isinstance(text, str) or not text.strip():
            context.user_data.pop("pending_audio", None)
            await self.responder_telegram(
                update, "La transcripción pendiente no es válida."
            )
            return
        completed = await self.procesar_prompt(
            update,
            context,
            text,
            progress_text="Transcripción confirmada. Enviando al modelo...",
            content_type="audio_transcription",
        )
        if completed:
            context.user_data.pop("pending_audio", None)


def build_application() -> Application:
    settings = Settings.from_env()
    requested_default = settings.codex_model.lower()
    default_model_key = next(
        (
            key
            for key, model in MODEL_ALIASES.items()
            if requested_default in {key, model}
        ),
        None,
    )
    if default_model_key is None:
        raise RuntimeError(
            "CODEX_MODEL debe ser sol, terra, luna o su identificador completo."
        )

    reasoning_by_model = {
        "luna": os.getenv("CODEX_REASONING_LUNA", "none").strip() or "none",
        "terra": os.getenv("CODEX_REASONING_TERRA", "none").strip() or "none",
        "sol": os.getenv("CODEX_REASONING_SOL", "medium").strip() or "medium",
    }
    reasoning_by_model[default_model_key] = settings.codex_reasoning_effort
    model_services = {
        key: CodexModelService(
            PROJECT_DIR,
            model=model,
            reasoning_effort=reasoning_by_model[key],
            codex_home=(
                settings.codex_home_plus
                if key == "sol"
                else settings.codex_home_free
            ),
        )
        for key, model in MODEL_ALIASES.items()
    }
    transcription = TranscriptionService(
        model_name=settings.whisper_model,
        device="cpu",
        compute_type="int8",
        language="es",
    )
    database_path = settings.conversation_database_path
    if not database_path.is_absolute():
        database_path = PROJECT_DIR / database_path
    agent = TelegramAgent(
        settings,
        model_services,
        default_model_key,
        transcription,
        HikingMapService(),
        HomeAssistantCalendarService(
            settings.home_assistant_url,
            settings.home_assistant_token,
            settings.family_calendar_entity_id,
        ),
        ConversationStore(database_path),
    )
    application = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(agent.start_service)
        .post_shutdown(agent.stop_service)
        .build()
    )
    agent.register_handlers(application)
    return application


def main() -> None:
    application = build_application()
    logger.info("Iniciando AgenteIA-local por Telegram")
    logger.info("Control de acceso activado")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )
