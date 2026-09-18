from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
from telegram import Bot, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agente_ia import (
    ApprovalError,
    CalendarDraftError,
    CalendarEventDraft,
    CalendarServiceError,
    CodexModelError,
    CodexModelService,
    Conversation,
    ConversationStore,
    CallablePlanningProvider,
    HikingMapService,
    HomeAssistantCalendarService,
    HomeAssistantShoppingListService,
    IntentKind,
    MapResult,
    MapServiceError,
    ModelResponse,
    PlanGenerationError,
    ShoppingListRequest,
    ShoppingListServiceError,
    TaskWorkflowError,
    TaskWorkflowService,
    TaskWorkflowStore,
    WorkflowOutcome,
    format_calendar_draft,
    format_calendar_events,
    format_shopping_confirmation,
    format_shopping_list,
    format_plan,
    parse_calendar_event_draft,
    parse_calendar_query,
    parse_shopping_list_request,
)
from agente_telegram.transcription_service import TranscriptionService
from agente_telegram.home_assistant_notification_bridge import (
    HomeAssistantNotificationBridge,
)
from agente_telegram.telegram_delivery import (
    DeliveryMode,
    EdgeSpeechSynthesizer,
    FixedTelegramChannel,
    TelegramEmitter,
)
from agente_telegram.voice_commands import ParsedVoiceCommand, parse_voice_command


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODEL_ALIASES = {
    "luna": "gpt-5.6-luna",
    "terra": "gpt-5.6-terra",
    "sol": "gpt-5.6-sol",
}
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807
APPROVAL_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def parse_approval_identifier(value: object) -> int | None:
    if (
        not isinstance(value, str)
        or len(value) > 19
        or re.fullmatch(r"[0-9]+", value) is None
    ):
        return None
    parsed = int(value)
    return parsed if 1 <= parsed <= MAX_SQLITE_INTEGER else None


def parse_model_selection(text: str) -> str:
    raw = text.strip().lower()
    if "=" in raw:
        return raw.split("=", 1)[1].strip().removeprefix("gpt-5.6-")
    parts = raw.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip().removeprefix("gpt-5.6-")
    return ""


def parse_env_boolean(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        f"{name} debe ser true/false, yes/no, on/off o 1/0."
    )

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
    notification_telegram_token: str | None
    notification_telegram_chat_id: int | None
    notification_tts_voice: str
    whisper_model: str
    codex_model: str
    codex_reasoning_effort: str
    codex_home_free: Path
    codex_home_plus: Path
    conversation_database_path: Path
    home_assistant_url: str
    home_assistant_token: str
    family_calendar_entity_id: str
    shopping_list_home_entity_id: str
    shopping_list_jessi_entity_id: str
    home_assistant_notification_bridge_enabled: bool
    task_approver_user_ids: tuple[int, ...] = ()

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
        approver_ids_text = os.getenv("TELEGRAM_TASK_APPROVER_USER_IDS", "").strip()
        try:
            parsed_approver_ids = tuple(
                dict.fromkeys(
                    int(value.strip())
                    for value in approver_ids_text.split(",")
                    if value.strip()
                )
            )
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_TASK_APPROVER_USER_IDS debe contener numeros separados por comas"
            ) from exc
        notification_token = os.getenv(
            "TELEGRAM_NOTIFICATIONS_BOT_TOKEN", ""
        ).strip()
        notification_chat_id_text = os.getenv(
            "TELEGRAM_NOTIFICATIONS_CHAT_ID", ""
        ).strip()
        if bool(notification_token) != bool(notification_chat_id_text):
            raise RuntimeError(
                "TELEGRAM_NOTIFICATIONS_BOT_TOKEN y "
                "TELEGRAM_NOTIFICATIONS_CHAT_ID deben configurarse juntos."
            )
        notification_chat_id: int | None = None
        if notification_chat_id_text:
            try:
                notification_chat_id = int(notification_chat_id_text)
            except ValueError as exc:
                raise RuntimeError(
                    "TELEGRAM_NOTIFICATIONS_CHAT_ID debe ser un número entero."
                ) from exc
            if notification_chat_id >= 0:
                raise RuntimeError(
                    "TELEGRAM_NOTIFICATIONS_CHAT_ID debe identificar un grupo "
                    "de Telegram (valor negativo)."
                )
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
            notification_telegram_token=notification_token or None,
            notification_telegram_chat_id=notification_chat_id,
            notification_tts_voice=(
                os.getenv(
                    "TELEGRAM_NOTIFICATIONS_TTS_VOICE", "es-ES-ElviraNeural"
                ).strip()
                or "es-ES-ElviraNeural"
            ),
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
            shopping_list_home_entity_id=os.getenv(
                "HOME_ASSISTANT_SHOPPING_LIST_HOME", "todo.casa"
            ).strip(),
            shopping_list_jessi_entity_id=os.getenv(
                "HOME_ASSISTANT_SHOPPING_LIST_JESSI", "todo.casa_jessi"
            ).strip(),
            home_assistant_notification_bridge_enabled=parse_env_boolean(
                "HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED"
            ),
            task_approver_user_ids=parsed_approver_ids,
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
        shopping_list_service: HomeAssistantShoppingListService,
        conversation_store: ConversationStore,
        telegram_emitter: TelegramEmitter | None = None,
        notification_channel: FixedTelegramChannel | None = None,
        task_workflow: TaskWorkflowService | None = None,
        home_assistant_notification_bridge: HomeAssistantNotificationBridge | None = None,
    ) -> None:
        self.settings = settings
        self.model_services = model_services
        self.default_model_key = default_model_key
        self.transcription = transcription
        self.map_service = map_service
        self.calendar_service = calendar_service
        self.shopping_list_service = shopping_list_service
        self.conversation_store = conversation_store
        self.telegram_emitter = telegram_emitter or TelegramEmitter()
        self.notification_channel = notification_channel
        self.home_assistant_notification_bridge = home_assistant_notification_bridge
        self.task_workflow = task_workflow or TaskWorkflowService(
            TaskWorkflowStore(conversation_store.database_path)
        )

    async def start_service(self, application: Application) -> None:
        del application
        self.conversation_store.initialize()
        self.task_workflow.store.initialize()
        if self.notification_channel is not None:
            await self.notification_channel.initialize()
        if self.home_assistant_notification_bridge is not None:
            self.home_assistant_notification_bridge.start()
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
        if self.home_assistant_notification_bridge is not None:
            await self.home_assistant_notification_bridge.stop()
        tasks = [service.close() for service in self.model_services.values()]
        if self.notification_channel is not None:
            tasks.append(self.notification_channel.shutdown())
        await asyncio.gather(*tasks)

    def register_handlers(self, application: Application) -> None:
        application.add_handler(
            MessageHandler(filters.ALL, self.confirmar_recepcion), group=-1
        )
        for command, callback in self.voice_command_handlers().items():
            # /modelo sigue aceptando la sintaxis existente /modelo=terra.
            if command != "modelo":
                application.add_handler(CommandHandler(command, callback))
        application.add_handler(
            CallbackQueryHandler(
                self.resolver_evento_calendario,
                pattern=r"^calendar:(?:confirm|cancel)$",
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.resolver_lista_compra,
                pattern=r"^shopping:(?:confirm|cancel)$",
            )
        )
        application.add_handler(
            MessageHandler(
                filters.TEXT & filters.Regex(r"^/modelo(?:=|\s|$)"),
                self.cambiar_modelo,
            )
        )
        application.add_handler(
            MessageHandler(filters.COMMAND, self.responder_texto)
        )
        application.add_handler(MessageHandler(filters.VOICE, self.recibir_voz))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.responder_texto)
        )

    def voice_command_handlers(
        self,
    ) -> dict[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]]:
        """Devuelve todos los comandos que pueden llegar desde una nota de voz."""
        return {
            "start": self.start,
            "mi_id": self.mostrar_id,
            "debug": self.cambiar_debug,
            "nuevo": self.nueva_conversacion,
            "conversaciones": self.listar_conversaciones,
            "abrir": self.abrir_conversacion,
            "historial": self.mostrar_historial,
            "ver_plan": self.ver_plan_tarea,
            "responder_tarea": self.responder_aclaracion_tarea,
            "aprobar_tarea": self.aprobar_tarea,
            "agenda": self.consultar_agenda,
            "evento": self.crear_evento_command,
            "lista": self.lista_compra_command,
            "compra": self.lista_compra_command,
            "aviso_texto": self.enviar_aviso_texto,
            "aviso_voz": self.enviar_aviso_voz,
            "aviso_ambos": self.enviar_aviso_ambos,
            "modelo": self.cambiar_modelo,
            "confirmar_audio": self.confirmar_audio,
            "corregido": self.corregir_audio,
            "corregir_audio": self.corregir_audio,
            "revisar": self.corregir_audio,
        }

    async def dispatch_voice_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        parsed: ParsedVoiceCommand,
    ) -> None:
        """Ejecuta un controlador existente con los argumentos transcritos."""
        handler = self.voice_command_handlers().get(parsed.name)
        if handler is None:
            return
        previous_args = context.args
        previous_command = getattr(context, "_voice_command_name", None)
        context.args = list(parsed.args)
        context._voice_command_name = parsed.name
        try:
            await handler(update, context)
        finally:
            context.args = previous_args
            if previous_command is None:
                context.__dict__.pop("_voice_command_name", None)
            else:
                context._voice_command_name = previous_command

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
        if update.message is None or update.effective_chat is None:
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
        await self.telegram_emitter.send_text(
            update.get_bot(),
            update.effective_chat.id,
            text,
            suffix=footer,
            reply_markup=reply_markup,
        )

    async def enviar_aviso_texto(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._enviar_aviso(update, context, DeliveryMode.TEXT)

    async def enviar_aviso_voz(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._enviar_aviso(update, context, DeliveryMode.VOICE)

    async def enviar_aviso_ambos(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        await self._enviar_aviso(update, context, DeliveryMode.BOTH)

    async def _enviar_aviso(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        mode: DeliveryMode,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        text = " ".join(context.args or []).strip()
        if not text:
            commands = {
                DeliveryMode.TEXT: "aviso_texto",
                DeliveryMode.VOICE: "aviso_voz",
                DeliveryMode.BOTH: "aviso_ambos",
            }
            await self.responder_telegram(
                update,
                f"Uso: /{commands[mode]} <mensaje>",
            )
            return
        if self.notification_channel is None:
            await self.responder_telegram(
                update,
                "El canal Bot Avisos Home Assistant no está configurado.",
            )
            return
        try:
            await self.notification_channel.send(text, mode)
        except Exception as exc:
            logger.error(
                "No se pudo enviar el aviso de Telegram: %s", type(exc).__name__
            )
            await self.responder_telegram(
                update,
                "No se ha podido enviar el aviso al grupo.",
            )
            return
        labels = {
            DeliveryMode.TEXT: "texto",
            DeliveryMode.VOICE: "voz",
            DeliveryMode.BOTH: "texto y voz",
        }
        await self.responder_telegram(
            update,
            f"Aviso enviado al grupo como {labels[mode]}.",
            provider="Bot Avisos Home Assistant",
            zero_token_operation=True,
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
            "En las notas de voz, empieza por «barra» para ejecutar un comando; "
            "si Whisper la omite, también se reconoce un comando inequívoco al "
            "principio. Por ejemplo, «barra agenda» o «barra aviso voz mensaje».\n\n"
            "Comandos:\n"
            "/nuevo [nombre] - crea y nombra una conversación\n"
            "/conversaciones - muestra tus últimas conversaciones\n"
            "/abrir <id> - continúa una conversación anterior\n"
            "/historial - muestra los últimos mensajes\n"
            "/agenda [días] - consulta el calendario familiar\n"
            "/evento <datos> - prepara un evento para confirmarlo\n"
            "/lista [casa|jessi] - consulta una lista de la compra\n"
            "/compra [casa|jessi] <productos> - añade productos\n"
            "/aviso_texto <mensaje> - prueba un aviso escrito en el grupo\n"
            "/aviso_voz <mensaje> - prueba un aviso hablado en el grupo\n"
            "/aviso_ambos <mensaje> - prueba texto y voz en el grupo\n"
            "/ver_plan [id] - muestra el ultimo plan de una tarea\n"
            "/responder_tarea <id> <respuesta> - aporta una aclaracion\n"
            "/aprobar_tarea <id> <version> <huella> - aprueba una version exacta\n"
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
            or update.effective_chat is None
        ):
            return

        command_text = update.message.text
        if command_text is None:
            command_text = "/modelo " + " ".join(context.args or [])
        requested = parse_model_selection(command_text)

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

    def _proveedor_planificacion(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session_id: int,
    ) -> tuple[CallablePlanningProvider, list[ModelResponse]]:
        service = self.servicio_activo(context)
        responses: list[ModelResponse] = []

        async def complete(prompt: str) -> str:
            response = await service.ask(session_id, prompt)
            responses.append(response)
            return response.text

        return CallablePlanningProvider(complete), responses

    async def _responder_resultado_tarea(
        self,
        update: Update,
        outcome: WorkflowOutcome,
        responses: list[ModelResponse],
    ) -> None:
        if outcome.task is None:
            return
        if outcome.questions:
            questions = "\n".join(f"- {question}" for question in outcome.questions)
            await self.responder_telegram(
                update,
                f"He registrado la tarea #{outcome.task.id}, pero faltan datos materiales:\n\n"
                f"{questions}\n\n"
                f"Responde con /responder_tarea {outcome.task.id} <respuesta>",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        if outcome.plan is None:
            await self.responder_telegram(
                update,
                f"La tarea #{outcome.task.id} ya estaba registrada con estado "
                f"{outcome.task.status}.",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        prefix = "" if outcome.created else "Solicitud duplicada: muestro el plan ya existente.\n\n"
        await self.responder_telegram(
            update,
            prefix + format_plan(outcome.plan),
            response=responses[-1] if responses else None,
            provider="Codex / ChatGPT",
            zero_token_operation=not responses,
        )

    async def ver_plan_tarea(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        conversation = self.conversacion_activa(update)
        argument = " ".join(context.args or []).strip()
        if argument and not argument.isdigit():
            await self.responder_telegram(update, "Uso: /ver_plan [id_tarea]")
            return
        task = (
            self.task_workflow.store.get_task(int(argument), conversation_id=conversation.id)
            if argument
            else self.task_workflow.store.latest_task(conversation.id)
        )
        if task is None:
            await self.responder_telegram(update, "No hay una tarea disponible en esta conversacion.")
            return
        plan = self.task_workflow.store.latest_plan(task.id)
        if plan is not None:
            await self.responder_telegram(
                update,
                format_plan(plan),
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        if task.missing_information:
            questions = "\n".join(f"- {question}" for question in task.missing_information)
            await self.responder_telegram(
                update,
                f"La tarea #{task.id} espera aclaraciones:\n\n{questions}\n\n"
                f"Usa /responder_tarea {task.id} <respuesta>",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        await self.responder_telegram(update, f"La tarea #{task.id} esta en estado {task.status}.")

    async def responder_aclaracion_tarea(
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
        args = list(context.args or [])
        if len(args) < 2 or not args[0].isdigit():
            await self.responder_telegram(
                update, "Uso: /responder_tarea <id_tarea> <respuesta>"
            )
            return
        task_id = int(args[0])
        answer = " ".join(args[1:]).strip()
        conversation = self.conversacion_activa(update)
        session_id = -((conversation.id << 32) + update.message.message_id)
        provider, responses = self._proveedor_planificacion(context, session_id)
        try:
            outcome = await self.task_workflow.clarify(
                task_id,
                conversation_id=conversation.id,
                source_key=f"telegram:{update.effective_chat.id}:{update.message.message_id}",
                answer=answer,
                provider=provider,
            )
        except (TaskWorkflowError, PlanGenerationError, CodexModelError, RuntimeError) as exc:
            logger.warning("No se pudo aclarar o planificar la tarea: %s", type(exc).__name__)
            await self.responder_telegram(update, f"No se ha podido actualizar la tarea.\n\n{exc}")
            return
        await self._responder_resultado_tarea(update, outcome, responses)

    async def aprobar_tarea(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        user = getattr(update, "effective_user", None)
        user_id = getattr(user, "id", None)
        if (
            user is None
            or isinstance(user_id, bool)
            or not isinstance(user_id, int)
            or not 1 <= user_id <= MAX_SQLITE_INTEGER
        ):
            return
        if not self.usuario_autorizado(update):
            return
        if user_id not in self.settings.task_approver_user_ids:
            await self.responder_telegram(
                update,
                "Tu usuario no tiene permiso para aprobar planes de ejecucion.",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return

        message = getattr(update, "message", None)
        chat = getattr(update, "effective_chat", None)
        message_id = getattr(message, "message_id", None)
        chat_id = getattr(chat, "id", None)
        if (
            message is None
            or chat is None
            or isinstance(message_id, bool)
            or not isinstance(message_id, int)
            or not 1 <= message_id <= MAX_SQLITE_INTEGER
            or isinstance(chat_id, bool)
            or not isinstance(chat_id, int)
            or chat_id == 0
            or abs(chat_id) > MAX_SQLITE_INTEGER
        ):
            return

        args = list(getattr(context, "args", None) or [])
        task_id = parse_approval_identifier(args[0]) if len(args) == 3 else None
        version = parse_approval_identifier(args[1]) if len(args) == 3 else None
        plan_hash = args[2] if len(args) == 3 and isinstance(args[2], str) else ""
        if (
            len(args) != 3
            or task_id is None
            or version is None
            or APPROVAL_HASH_PATTERN.fullmatch(plan_hash) is None
        ):
            await self.responder_telegram(
                update, "Uso: /aprobar_tarea <id_tarea> <version> <huella>"
            )
            return

        try:
            conversation = self.conversacion_activa(update)
            approval = self.task_workflow.approve(
                task_id,
                conversation_id=conversation.id,
                version=version,
                plan_hash=plan_hash,
                approved_by=user_id,
                source_key=f"telegram:{chat_id}:{message_id}",
            )
        except ApprovalError as exc:
            await self.responder_telegram(
                update,
                f"No se ha podido aprobar el plan: {exc}",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        except Exception as exc:
            logger.warning("Fallo interno al aprobar una tarea: %s", type(exc).__name__)
            await self.responder_telegram(
                update,
                "No se ha podido aprobar el plan por un error interno.",
                provider="triaje interno",
                zero_token_operation=True,
            )
            return
        await self.responder_telegram(
            update,
            f"Plan aprobado: tarea #{approval.task_id}, version {approval.plan_version}, "
            f"huella {approval.plan_hash}.\n\nLa aprobacion queda registrada; no se ha ejecutado nada.",
            provider="triaje interno",
            zero_token_operation=True,
        )

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

    async def lista_compra_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self.usuario_autorizado(update) or update.message is None:
            return
        command_text = update.message.text
        if command_text is None:
            command = "/" + getattr(context, "_voice_command_name", "lista")
        else:
            command = command_text.split(maxsplit=1)[0].split("@", 1)[0].lower()
        argument = " ".join(context.args or []).strip()
        prompt = f"{command} {argument}".strip()
        await self.procesar_prompt(
            update,
            context,
            prompt,
            progress_text="Gestionando la lista de la compra...",
            content_type="shopping_list_request",
        )

    async def resolver_lista_compra(
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
        request = context.user_data.get("pending_shopping_request")
        if not isinstance(request, ShoppingListRequest):
            await callback.edit_message_text(
                "Esta operación ha caducado. Envía de nuevo la petición."
            )
            return
        if callback.data == "shopping:cancel":
            context.user_data.pop("pending_shopping_request", None)
            await callback.edit_message_text(
                "❌ Operación cancelada. No se ha modificado la lista.\n\n"
                + self.pie_operacion_sin_tokens("interno")
            )
            return

        started_at = perf_counter()
        try:
            text = await self.ejecutar_lista_compra(request)
        except ShoppingListServiceError as exc:
            logger.warning("No se pudo modificar la lista: %s", type(exc).__name__)
            await callback.edit_message_text(
                f"No se ha podido modificar la lista.\n\n{exc}\n\n"
                + self.pie_operacion_sin_tokens("Home Assistant")
            )
            return
        context.user_data.pop("pending_shopping_request", None)
        text += "\n\n" + self.pie_operacion_sin_tokens(
            "Home Assistant", elapsed_seconds=perf_counter() - started_at
        )
        await callback.edit_message_text(text)
        if update.effective_chat is not None:
            conversation = self.conversacion_activa(update)
            self.conversation_store.save_message(
                conversation.id,
                update.effective_chat.id,
                telegram_message_id=None,
                direction="outgoing",
                content_type="shopping_list",
                text=text.split("\n\n⏱️", 1)[0],
            )

    async def ejecutar_lista_compra(self, request: ShoppingListRequest) -> str:
        name = self.shopping_list_service.display_name(request.list_key)
        if request.operation == "list":
            items = await self.shopping_list_service.items(request.list_key)
            return format_shopping_list(name, items)
        if request.operation == "add":
            await self.shopping_list_service.add_items(request.list_key, request.items)
            products = "\n".join(f"• {item}" for item in request.items)
            return f"✅ Añadido a {name}:\n\n{products}"
        if request.operation == "complete":
            await self.shopping_list_service.complete_items(request.list_key, request.items)
            products = "\n".join(f"• {item}" for item in request.items)
            return f"✅ Marcado como comprado en {name}:\n\n{products}"
        if request.operation == "remove":
            await self.shopping_list_service.remove_items(request.list_key, request.items)
            products = "\n".join(f"• {item}" for item in request.items)
            return f"✅ Eliminado de {name}:\n\n{products}"
        await self.shopping_list_service.clear_completed(request.list_key)
        return f"✅ Productos comprados eliminados de {name}."

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
        shopping_request = parse_shopping_list_request(prompt)
        if shopping_request is not None:
            if shopping_request.needs_confirmation:
                context.user_data["pending_shopping_request"] = shopping_request
                preview = format_shopping_confirmation(shopping_request)
                keyboard = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton(
                            "✅ Confirmar", callback_data="shopping:confirm"
                        ),
                        InlineKeyboardButton(
                            "❌ Cancelar", callback_data="shopping:cancel"
                        ),
                    ]]
                )
                self.conversation_store.save_message(
                    conversation.id,
                    update.effective_chat.id,
                    telegram_message_id=None,
                    direction="outgoing",
                    content_type="shopping_list_preview",
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
            try:
                text = await self.ejecutar_lista_compra(shopping_request)
            except ShoppingListServiceError as exc:
                logger.warning("No se pudo gestionar la lista: %s", type(exc).__name__)
                await self.responder_telegram(
                    update,
                    str(exc),
                    provider="Home Assistant",
                    zero_token_operation=True,
                )
                return False
            self.conversation_store.save_message(
                conversation.id,
                update.effective_chat.id,
                telegram_message_id=None,
                direction="outgoing",
                content_type="shopping_list",
                text=text,
            )
            await self.responder_telegram(
                update,
                text,
                provider="Home Assistant",
                zero_token_operation=True,
            )
            return True
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

        planning_session_id = -((conversation.id << 32) + update.message.message_id)
        planning_provider, planning_responses = self._proveedor_planificacion(
            context, planning_session_id
        )
        try:
            task_outcome = await self.task_workflow.submit(
                conversation_id=conversation.id,
                source_key=f"telegram:{update.effective_chat.id}:{update.message.message_id}",
                request_text=prompt,
                provider=planning_provider,
            )
        except (TaskWorkflowError, PlanGenerationError, CodexModelError, RuntimeError) as exc:
            logger.warning("No se pudo construir el plan de tarea: %s", type(exc).__name__)
            await self.responder_telegram(
                update,
                "He detectado una solicitud de trabajo, pero no se ha podido construir "
                f"un plan valido. No se ha ejecutado nada.\n\n{exc}",
            )
            return False
        if task_outcome.task is not None:
            await self._responder_resultado_tarea(update, task_outcome, planning_responses)
            return True
        if task_outcome.decision.kind is IntentKind.CLARIFICATION:
            await self.responder_telegram(
                update,
                "No puedo determinar con seguridad si solicitas una explicacion o un trabajo. "
                "Indica la accion concreta, el objetivo y, si corresponde, el proyecto o ruta.",
                provider="triaje interno",
                zero_token_operation=True,
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

            parsed_command = parse_voice_command(
                text, self.voice_command_handlers().keys()
            )
            if parsed_command is not None:
                await self.responder_debug(
                    update,
                    context,
                    f"Comando hablado reconocido: /{parsed_command.name}",
                )
                await self.dispatch_voice_command(update, context, parsed_command)
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
    telegram_emitter = TelegramEmitter(
        synthesizer=EdgeSpeechSynthesizer(settings.notification_tts_voice)
    )
    notification_channel = None
    if (
        settings.notification_telegram_token is not None
        and settings.notification_telegram_chat_id is not None
    ):
        notification_channel = FixedTelegramChannel(
            Bot(token=settings.notification_telegram_token),
            settings.notification_telegram_chat_id,
            telegram_emitter,
        )
    home_assistant_notification_bridge = None
    if settings.home_assistant_notification_bridge_enabled:
        if notification_channel is None:
            raise RuntimeError(
                "HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED requiere el bot "
                "y el grupo de notificaciones de Telegram."
            )
        if not settings.home_assistant_url or not settings.home_assistant_token:
            raise RuntimeError(
                "HOME_ASSISTANT_NOTIFICATION_BRIDGE_ENABLED requiere "
                "HOME_ASSISTANT_URL y HOME_ASSISTANT_TOKEN."
            )
        home_assistant_notification_bridge = HomeAssistantNotificationBridge(
            settings.home_assistant_url,
            settings.home_assistant_token,
            notification_channel,
        )
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
        HomeAssistantShoppingListService(
            settings.home_assistant_url,
            settings.home_assistant_token,
            {
                "casa": settings.shopping_list_home_entity_id,
                "casa_jessi": settings.shopping_list_jessi_entity_id,
            },
        ),
        ConversationStore(database_path),
        telegram_emitter=telegram_emitter,
        notification_channel=notification_channel,
        home_assistant_notification_bridge=home_assistant_notification_bridge,
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
