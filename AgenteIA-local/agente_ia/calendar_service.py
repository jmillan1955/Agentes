from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import httpx


class CalendarServiceError(RuntimeError):
    """Error al consultar el calendario familiar mediante Home Assistant."""


class CalendarDraftError(ValueError):
    """La petición parece crear un evento, pero faltan datos fiables."""


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    summary: str
    start: datetime | date
    end: datetime | date
    location: str | None = None
    description: str | None = None

    @property
    def all_day(self) -> bool:
        return isinstance(self.start, date) and not isinstance(self.start, datetime)


@dataclass(frozen=True, slots=True)
class CalendarQuery:
    start: datetime
    end: datetime
    label: str


@dataclass(frozen=True, slots=True)
class CalendarEventDraft:
    summary: str
    start: datetime
    end: datetime
    location: str | None = None


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text)
    return "".join(
        character for character in value if not unicodedata.combining(character)
    ).lower().strip()


def parse_calendar_query(text: str, *, now: datetime | None = None) -> CalendarQuery | None:
    normalized = _normalize(text)
    is_command = normalized.startswith("/agenda")
    mentions_calendar = any(word in normalized for word in ("agenda", "calendario"))
    natural_shortcut = re.search(
        r"\b(?:que tenemos|que hay)\s+(?:hoy|manana|esta semana)\b",
        normalized,
    )
    if not (is_command or mentions_calendar or natural_shortcut):
        return None

    current = now or datetime.now().astimezone()
    midnight = datetime.combine(current.date(), time.min, tzinfo=current.tzinfo)

    if "pasado manana" in normalized:
        start = midnight + timedelta(days=2)
        return CalendarQuery(start, start + timedelta(days=1), "pasado mañana")
    if "manana" in normalized:
        start = midnight + timedelta(days=1)
        return CalendarQuery(start, start + timedelta(days=1), "mañana")
    if "hoy" in normalized:
        return CalendarQuery(current, midnight + timedelta(days=1), "hoy")
    if "esta semana" in normalized:
        next_monday = midnight + timedelta(days=7 - midnight.weekday())
        return CalendarQuery(current, next_monday, "esta semana")

    days_match = re.search(r"(?:proximos?\s+)?(\d{1,2})\s+dias?", normalized)
    if days_match is None and is_command:
        days_match = re.search(r"^/agenda\s+(\d{1,2})\b", normalized)
    days = min(max(int(days_match.group(1)), 1), 31) if days_match else 7
    return CalendarQuery(current, current + timedelta(days=days), f"los próximos {days} días")


def is_calendar_creation_request(text: str) -> bool:
    normalized = _normalize(text)
    has_action = re.search(
        r"\b(?:anade|agrega|crea|apunta|pon)\b", normalized
    ) is not None
    has_calendar = re.search(r"\b(?:calendario|agenda)\b", normalized) is not None
    return has_action and has_calendar


def parse_calendar_event_draft(
    text: str, *, now: datetime | None = None
) -> CalendarEventDraft | None:
    original = text.strip()
    if not is_calendar_creation_request(original):
        return None
    normalized = _normalize(original)
    pattern = re.compile(
        r"\b(?:calendario|agenda)(?:\s+familiar)?(?:\s+un evento)?\s+"
        r"(?P<summary>.+?)\s+"
        r"(?P<day>pasado manana|manana|hoy|el\s+\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+"
        r"(?:a\s+las?|a)\s+(?P<hour>\d{1,2})"
        r"(?:(?::|\.)(?P<minute>\d{2}))?(?:\s*horas?)?"
        r"(?P<tail>.*)$"
    )
    match = pattern.search(normalized)
    if match is None:
        raise CalendarDraftError(
            "Indica título, día y hora. Ejemplo: Añade al calendario familiar "
            "Dentista mañana a las 18:00 durante 45 minutos."
        )

    summary = original[match.start("summary") : match.end("summary")].strip(" ,.;:")
    if not summary:
        raise CalendarDraftError("El evento necesita un título.")

    current = now or datetime.now().astimezone()
    day_text = match.group("day")
    if day_text == "hoy":
        event_date = current.date()
    elif day_text == "manana":
        event_date = current.date() + timedelta(days=1)
    elif day_text == "pasado manana":
        event_date = current.date() + timedelta(days=2)
    else:
        date_parts = [int(value) for value in re.findall(r"\d+", day_text)]
        day, month = date_parts[:2]
        year = date_parts[2] if len(date_parts) == 3 else current.year
        if year < 100:
            year += 2000
        try:
            event_date = date(year, month, day)
        except ValueError as exc:
            raise CalendarDraftError("La fecha indicada no es válida.") from exc
        if len(date_parts) == 2 and event_date < current.date():
            event_date = date(year + 1, month, day)

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    if hour > 23 or minute > 59:
        raise CalendarDraftError("La hora indicada no es válida.")

    normalized_tail = match.group("tail")
    original_tail = original[match.start("tail") : match.end("tail")]
    duration_match = re.search(
        r"\bdurante\s+(\d{1,3})\s*(minutos?|mins?|horas?|h)\b",
        normalized_tail,
    )
    duration_minutes = 60
    if duration_match is not None:
        duration_minutes = int(duration_match.group(1))
        if duration_match.group(2).startswith("hora") or duration_match.group(2) == "h":
            duration_minutes *= 60
    if not 1 <= duration_minutes <= 1440:
        raise CalendarDraftError("La duración debe estar entre 1 minuto y 24 horas.")

    location = None
    location_match = re.search(
        r"\ben\s+(.+?)(?=\s+durante\b|$)", normalized_tail
    )
    if location_match is not None:
        location = original_tail[
            location_match.start(1) : location_match.end(1)
        ].strip(" ,.;:") or None

    start = datetime.combine(event_date, time(hour, minute), tzinfo=current.tzinfo)
    return CalendarEventDraft(
        summary=summary,
        start=start,
        end=start + timedelta(minutes=duration_minutes),
        location=location,
    )


class HomeAssistantCalendarService:
    def __init__(
        self,
        base_url: str,
        token: str,
        entity_id: str,
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.token = token.strip()
        self.entity_id = entity_id.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token and self.entity_id)

    async def events(self, query: CalendarQuery) -> list[CalendarEvent]:
        if not self.configured:
            raise CalendarServiceError(
                "El calendario de Home Assistant todavía no está configurado."
            )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        params = {"start": query.start.isoformat(), "end": query.end.isoformat()}
        url = f"{self.base_url}/api/calendars/{self.entity_id}"
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CalendarServiceError(
                "Home Assistant no ha podido devolver el calendario familiar."
            ) from exc
        if not isinstance(payload, list):
            raise CalendarServiceError("Home Assistant ha devuelto una respuesta no válida.")
        return [self._parse_event(item) for item in payload if isinstance(item, dict)]

    async def create_event(self, draft: CalendarEventDraft) -> None:
        if not self.configured:
            raise CalendarServiceError(
                "El calendario de Home Assistant todavía no está configurado."
            )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "entity_id": self.entity_id,
            "summary": draft.summary,
            "start_date_time": draft.start.isoformat(),
            "end_date_time": draft.end.isoformat(),
        }
        if draft.location:
            payload["location"] = draft.location
        url = f"{self.base_url}/api/services/google/create_event"
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CalendarServiceError(
                "Home Assistant no ha podido crear el evento en Google Calendar."
            ) from exc

    @staticmethod
    def _parse_event(item: dict[str, Any]) -> CalendarEvent:
        try:
            start = HomeAssistantCalendarService._parse_moment(item["start"])
            end = HomeAssistantCalendarService._parse_moment(item["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CalendarServiceError("Hay un evento con fechas no válidas.") from exc
        return CalendarEvent(
            summary=str(item.get("summary") or "Sin título"),
            start=start,
            end=end,
            location=str(item["location"]) if item.get("location") else None,
            description=str(item["description"]) if item.get("description") else None,
        )

    @staticmethod
    def _parse_moment(value: dict[str, Any]) -> datetime | date:
        if "dateTime" in value:
            return datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
        if "date" in value:
            return date.fromisoformat(str(value["date"]))
        raise ValueError("La fecha no contiene dateTime ni date")


def format_calendar_events(events: list[CalendarEvent], label: str) -> str:
    if not events:
        return f"No hay eventos en Familia Millan Romero {label}."

    lines = [f"Familia Millan Romero — {label}:"]
    for event in events:
        if event.all_day:
            when = event.start.strftime("%d/%m") + " · todo el día"
        else:
            start = event.start
            assert isinstance(start, datetime)
            local_start = start.astimezone()
            weekdays = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
            when = (
                f"{weekdays[local_start.weekday()]} "
                f"{local_start:%d/%m · %H:%M}"
            )
        line = f"• {when} — {event.summary}"
        if event.location:
            line += f"\n  📍 {event.location}"
        lines.append(line)
    return "\n".join(lines)


def format_calendar_draft(draft: CalendarEventDraft) -> str:
    weekdays = (
        "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
    )
    lines = [
        "Evento pendiente de confirmación:",
        "",
        f"📌 {draft.summary}",
        f"📅 {weekdays[draft.start.weekday()]} {draft.start:%d/%m/%Y}",
        f"🕒 {draft.start:%H:%M}–{draft.end:%H:%M}",
    ]
    if draft.location:
        lines.append(f"📍 {draft.location}")
    lines.append("\n¿Quieres guardarlo en Familia Millan Romero?")
    return "\n".join(lines)
