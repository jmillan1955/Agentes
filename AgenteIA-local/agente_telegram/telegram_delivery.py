from __future__ import annotations

import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


TELEGRAM_TEXT_LIMIT = 4096


class DeliveryMode(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    BOTH = "both"


class TelegramBot(Protocol):
    async def send_message(self, **kwargs: Any) -> Any: ...

    async def send_voice(self, **kwargs: Any) -> Any: ...


class SpeechSynthesizer(Protocol):
    async def synthesize(self, text: str, output_path: Path) -> None: ...


class EdgeSpeechSynthesizer:
    """Generate an MP3 suitable for Telegram voice messages with edge-tts."""

    def __init__(self, voice: str = "es-ES-ElviraNeural") -> None:
        self.voice = voice

    async def synthesize(self, text: str, output_path: Path) -> None:
        # Keep the optional network-backed dependency out of text-only startup.
        import edge_tts

        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        await communicate.save(str(output_path))


def split_telegram_text(
    text: str,
    *,
    suffix: str = "",
    limit: int = TELEGRAM_TEXT_LIMIT,
) -> list[str]:
    """Split text at readable boundaries and append ``suffix`` to every part."""

    separator = "\n\n" if suffix else ""
    available = limit - len(separator) - len(suffix)
    if available < 1:
        raise ValueError("El pie de Telegram ocupa todo el mensaje disponible.")

    remaining = text.strip() or "Respuesta vacía"
    fragments: list[str] = []
    while remaining:
        if len(remaining) <= available:
            fragment, remaining = remaining, ""
        else:
            split_at = remaining.rfind("\n", 0, available + 1)
            if split_at < available // 2:
                split_at = remaining.rfind(" ", 0, available + 1)
            if split_at <= 0:
                split_at = available
            fragment = remaining[:split_at].rstrip()
            remaining = remaining[split_at:].lstrip()
        fragments.append(f"{fragment}{separator}{suffix}")
    return fragments


class TelegramEmitter:
    """Common Telegram output used by conversations and fixed notifications."""

    def __init__(
        self,
        *,
        synthesizer: SpeechSynthesizer | None = None,
        temp_root: Path | None = None,
    ) -> None:
        self.synthesizer = synthesizer
        self.temp_root = temp_root

    async def send_text(
        self,
        bot: TelegramBot,
        chat_id: int,
        text: str,
        *,
        suffix: str = "",
        reply_markup: Any = None,
    ) -> None:
        fragments = split_telegram_text(text, suffix=suffix)
        for index, fragment in enumerate(fragments):
            await bot.send_message(
                chat_id=chat_id,
                text=fragment,
                reply_markup=reply_markup if index == len(fragments) - 1 else None,
            )

    async def send_voice(
        self,
        bot: TelegramBot,
        chat_id: int,
        text: str,
    ) -> None:
        if self.synthesizer is None:
            raise RuntimeError("La síntesis de voz no está configurada.")
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("No se puede sintetizar un mensaje vacío.")

        root = str(self.temp_root) if self.temp_root is not None else None
        with tempfile.TemporaryDirectory(prefix="agenteia-tts-", dir=root) as directory:
            audio_path = Path(directory) / "aviso.mp3"
            await self.synthesizer.synthesize(clean_text, audio_path)
            if not audio_path.is_file() or audio_path.stat().st_size == 0:
                raise RuntimeError("El sintetizador no generó un audio válido.")
            with audio_path.open("rb") as audio_file:
                await bot.send_voice(chat_id=chat_id, voice=audio_file)

    async def send(
        self,
        bot: TelegramBot,
        chat_id: int,
        text: str,
        mode: DeliveryMode,
    ) -> None:
        if mode in {DeliveryMode.TEXT, DeliveryMode.BOTH}:
            await self.send_text(bot, chat_id, text)
        if mode in {DeliveryMode.VOICE, DeliveryMode.BOTH}:
            await self.send_voice(bot, chat_id, text)


class FixedTelegramChannel:
    """Telegram channel locked to one bot credential and one destination."""

    def __init__(
        self,
        bot: TelegramBot,
        chat_id: int,
        emitter: TelegramEmitter,
    ) -> None:
        self._bot = bot
        self.chat_id = chat_id
        self._emitter = emitter

    async def initialize(self) -> None:
        initialize = getattr(self._bot, "initialize", None)
        if initialize is not None:
            await initialize()

    async def shutdown(self) -> None:
        shutdown = getattr(self._bot, "shutdown", None)
        if shutdown is not None:
            await shutdown()

    async def send(self, text: str, mode: DeliveryMode) -> None:
        await self._emitter.send(self._bot, self.chat_id, text, mode)
