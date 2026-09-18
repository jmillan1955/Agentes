"""Reconocimiento de comandos de Telegram pronunciados en notas de voz."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ParsedVoiceCommand:
    """Comando reconocido y argumentos conservando el texto transcrito."""

    name: str
    args: tuple[str, ...]


def _spoken_words(value: str) -> list[str]:
    """Devuelve palabras comparables, ignorando acentos y separadores."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    ).lower()
    normalized = normalized.replace("_", " ").replace("-", " ")
    return re.findall(r"[a-z0-9]+", normalized)


def parse_voice_command(
    transcription: str,
    command_names: Iterable[str],
) -> ParsedVoiceCommand | None:
    """Reconoce una transcripción que empieza por ``barra`` o un comando.

    Los nombres registrados se comparan también con sus guiones bajos
    sustituidos por espacios. Así, ``barra aviso voz mensaje`` se convierte
    en ``aviso_voz`` y sólo ``mensaje`` llega como argumento. Se admite omitir
    ``barra`` únicamente cuando las primeras palabras son inequívocamente un
    nombre de comando registrado.
    """
    raw_words = transcription.strip().split()
    if not raw_words:
        return None

    token_words: list[tuple[str, int]] = []
    for index, raw_word in enumerate(raw_words):
        token_words.extend((word, index) for word in _spoken_words(raw_word))
    if not token_words:
        return None

    command_start = 1 if token_words[0][0] == "barra" else 0
    aliases = {"estar": "start", "estart": "start"}
    candidates: list[tuple[int, str, list[str]]] = []
    for name in command_names:
        words = _spoken_words(name)
        if words:
            candidates.append((len(words), name, words))
    candidates.sort(key=lambda item: item[0], reverse=True)

    for word_count, name, command_words in candidates:
        spoken = [
            word
            for word, _ in token_words[command_start : command_start + word_count]
        ]
        spoken = [aliases.get(word, word) for word in spoken]
        expected = [aliases.get(word, word) for word in command_words]
        if spoken != expected:
            continue
        command_end_token = token_words[command_start + word_count - 1][1]
        args = tuple(raw_words[command_end_token + 1 :])
        return ParsedVoiceCommand(name=name, args=args)
    return None
