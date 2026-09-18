from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from agente_telegram.telegram_delivery import DeliveryMode, FixedTelegramChannel


logger = logging.getLogger(__name__)

EVENT_TYPE = "agenteia_notification"
MAX_TITLE_LENGTH = 200
MAX_MESSAGE_LENGTH = 12_000
SUBSCRIPTION_ID = 1


class HomeAssistantBridgeError(RuntimeError):
    """Raised for WebSocket protocol or configuration errors."""


@dataclass(frozen=True, slots=True)
class HomeAssistantNotification:
    title: str
    message: str
    mode: DeliveryMode

    @property
    def telegram_text(self) -> str:
        if self.title:
            return f"{self.title}\n\n{self.message}"
        return self.message


def websocket_url(home_assistant_url: str) -> str:
    parsed = urlsplit(home_assistant_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("HOME_ASSISTANT_URL debe ser una URL HTTP o HTTPS válida.")
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    return urlunsplit((scheme, parsed.netloc, f"{base_path}/api/websocket", "", ""))


def parse_notification(data: object) -> HomeAssistantNotification:
    if not isinstance(data, dict):
        raise ValueError("event.data debe ser un objeto.")
    allowed_keys = {"titulo", "mensaje", "modo"}
    unknown_keys = set(data) - allowed_keys
    if unknown_keys:
        raise ValueError("event.data contiene campos no permitidos.")

    raw_title = data.get("titulo", "")
    raw_message = data.get("mensaje")
    raw_mode = data.get("modo")
    if not isinstance(raw_title, str):
        raise ValueError("titulo debe ser texto.")
    if not isinstance(raw_message, str):
        raise ValueError("mensaje es obligatorio y debe ser texto.")
    if not isinstance(raw_mode, str):
        raise ValueError("modo es obligatorio y debe ser texto.")

    title = raw_title.strip()
    message = raw_message.strip()
    mode_text = raw_mode.strip()
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"titulo supera {MAX_TITLE_LENGTH} caracteres.")
    if not message:
        raise ValueError("mensaje no puede estar vacío.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"mensaje supera {MAX_MESSAGE_LENGTH} caracteres.")
    try:
        mode = DeliveryMode(mode_text)
    except ValueError as exc:
        raise ValueError("modo debe ser text, voice o both.") from exc
    return HomeAssistantNotification(title, message, mode)


SessionFactory = Callable[[], Any]
Sleep = Callable[[float], Awaitable[None]]


class HomeAssistantNotificationBridge:
    """Subscribe to one HA event over an authenticated outbound WebSocket."""

    def __init__(
        self,
        home_assistant_url: str,
        token: str,
        channel: FixedTelegramChannel,
        *,
        session_factory: SessionFactory = aiohttp.ClientSession,
        sleep: Sleep = asyncio.sleep,
        initial_backoff: float = 1.0,
        maximum_backoff: float = 60.0,
    ) -> None:
        if not token.strip():
            raise ValueError("HOME_ASSISTANT_TOKEN es obligatorio para el puente.")
        self.websocket_url = websocket_url(home_assistant_url)
        self._token = token.strip()
        self._channel = channel
        self._session_factory = session_factory
        self._sleep = sleep
        self._initial_backoff = initial_backoff
        self._maximum_backoff = maximum_backoff
        self._stop_requested = False
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._stop_requested = False
        self._task = asyncio.create_task(
            self.run_forever(), name="home-assistant-notification-bridge"
        )
        logger.info(
            "Puente de avisos de Home Assistant iniciado mediante WebSocket saliente"
        )

    async def stop(self) -> None:
        self._stop_requested = True
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        logger.info("Puente de avisos de Home Assistant detenido")

    async def run_forever(self) -> None:
        backoff = self._initial_backoff
        while not self._stop_requested:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Puente de Home Assistant desconectado (%s); se reintentará",
                    type(exc).__name__,
                )
            if self._stop_requested:
                break
            await self._sleep(backoff)
            backoff = min(backoff * 2, self._maximum_backoff)

    async def _connect_once(self) -> None:
        async with self._session_factory() as session:
            async with session.ws_connect(
                self.websocket_url,
                heartbeat=30,
            ) as websocket:
                await self._authenticate_and_subscribe(websocket)
                logger.info(
                    "Puente suscrito al evento %s de Home Assistant", EVENT_TYPE
                )
                async for message in websocket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_websocket_text(message.data)
                    elif message.type in {
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                    }:
                        break
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        raise HomeAssistantBridgeError(
                            "Home Assistant cerró el WebSocket con error."
                        )

    async def _authenticate_and_subscribe(self, websocket: Any) -> None:
        auth_required = await websocket.receive_json()
        if (
            not isinstance(auth_required, dict)
            or auth_required.get("type") != "auth_required"
        ):
            raise HomeAssistantBridgeError(
                "Home Assistant no inició el protocolo de autenticación."
            )
        await websocket.send_json(
            {"type": "auth", "access_token": self._token}
        )
        auth_result = await websocket.receive_json()
        if not isinstance(auth_result, dict) or auth_result.get("type") != "auth_ok":
            raise HomeAssistantBridgeError(
                "Home Assistant rechazó la autenticación del puente."
            )
        await websocket.send_json(
            {
                "id": SUBSCRIPTION_ID,
                "type": "subscribe_events",
                "event_type": EVENT_TYPE,
            }
        )
        subscription_result = await websocket.receive_json()
        if (
            not isinstance(subscription_result, dict)
            or subscription_result.get("id") != SUBSCRIPTION_ID
            or subscription_result.get("type") != "result"
            or subscription_result.get("success") is not True
        ):
            raise HomeAssistantBridgeError(
                "Home Assistant rechazó la suscripción al evento de avisos."
            )

    async def _handle_websocket_text(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Mensaje WebSocket de Home Assistant no válido ignorado")
            return
        if not isinstance(payload, dict) or payload.get("type") != "event":
            return
        event = payload.get("event")
        if not isinstance(event, dict) or event.get("event_type") != EVENT_TYPE:
            return
        try:
            notification = parse_notification(event.get("data"))
        except ValueError as exc:
            logger.warning("Aviso de Home Assistant ignorado: %s", exc)
            return
        try:
            await self._channel.send(notification.telegram_text, notification.mode)
        except Exception as exc:
            logger.error(
                "No se pudo entregar el aviso de Home Assistant (%s)",
                type(exc).__name__,
            )
            return
        logger.info(
            "Aviso de Home Assistant entregado por Telegram en modo %s",
            notification.mode.value,
        )
