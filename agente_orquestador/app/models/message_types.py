from __future__ import annotations

from enum import StrEnum


class ChannelName(StrEnum):
    CONSOLE = "console"
    TELEGRAM = "telegram"


class ContentType(StrEnum):
    TEXT = "text"
    COMMAND = "command"
    AUDIO = "audio"
    DOCUMENT = "document"
    IMAGE = "image"