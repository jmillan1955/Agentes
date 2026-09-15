from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx

from agente_ia.calendar_service import (
    CalendarDraftError,
    CalendarServiceError,
    HomeAssistantCalendarService,
    format_calendar_draft,
    format_calendar_events,
    parse_calendar_event_draft,
    parse_calendar_query,
)


NOW = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


class CalendarQueryTests(unittest.TestCase):
    def test_detects_natural_query_for_tomorrow(self) -> None:
        query = parse_calendar_query("¿Qué tenemos mañana en el calendario?", now=NOW)

        self.assertIsNotNone(query)
        assert query is not None
        self.assertEqual(query.label, "mañana")
        self.assertEqual(query.start.day, 16)

    def test_command_accepts_number_of_days(self) -> None:
        query = parse_calendar_query("/agenda 14", now=NOW)

        self.assertIsNotNone(query)
        assert query is not None
        self.assertEqual((query.end - query.start).days, 14)

    def test_does_not_intercept_general_question(self) -> None:
        self.assertIsNone(parse_calendar_query("¿Qué diferencia hay entre fecha y hora?", now=NOW))


class CalendarDraftTests(unittest.TestCase):
    def test_accepts_whisper_hour_wording(self) -> None:
        draft = parse_calendar_event_draft(
            "Añade al calendario familiar prueba agenteIA mañana a las 19 horas "
            "durante 15 minutos.",
            now=NOW,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.start.hour, 19)
        self.assertEqual(draft.start.minute, 0)
        self.assertEqual((draft.end - draft.start).seconds // 60, 15)

    def test_parses_natural_event_with_duration_and_location(self) -> None:
        draft = parse_calendar_event_draft(
            "Añade al calendario familiar Dentista mañana a las 18:00 "
            "durante 45 minutos en Clínica X",
            now=NOW,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.summary, "Dentista")
        self.assertEqual(draft.start.day, 16)
        self.assertEqual(draft.start.hour, 18)
        self.assertEqual((draft.end - draft.start).seconds // 60, 45)
        self.assertEqual(draft.location, "Clínica X")
        self.assertIn("Evento pendiente de confirmación", format_calendar_draft(draft))

    def test_uses_one_hour_as_default_duration(self) -> None:
        draft = parse_calendar_event_draft(
            "Pon en el calendario Reunión el 20/09/2026 a las 09:30",
            now=NOW,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual((draft.end - draft.start).seconds // 60, 60)

    def test_requires_reliable_date_and_time(self) -> None:
        with self.assertRaises(CalendarDraftError):
            parse_calendar_event_draft(
                "Añade al calendario una cita algún día por la tarde",
                now=NOW,
            )


class HomeAssistantCalendarTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_formats_google_calendar_event(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "Bearer secreto")
            self.assertIn("calendar.familia_millan_romero", str(request.url))
            return httpx.Response(
                200,
                json=[
                    {
                        "summary": "Recogida de Alejandro",
                        "start": {"dateTime": "2026-09-16T15:30:00+02:00"},
                        "end": {"dateTime": "2026-09-16T16:00:00+02:00"},
                        "location": "Guardería La Abeja Maya",
                    }
                ],
            )

        service = HomeAssistantCalendarService(
            "http://homeassistant.local:8123",
            "secreto",
            "calendar.familia_millan_romero",
            transport=httpx.MockTransport(handler),
        )
        query = parse_calendar_query("agenda mañana", now=NOW)
        assert query is not None

        events = await service.events(query)
        result = format_calendar_events(events, query.label)

        self.assertIn("Recogida de Alejandro", result)
        self.assertIn("Guardería La Abeja Maya", result)
        self.assertIn("15:30", result)

    async def test_requires_complete_configuration(self) -> None:
        service = HomeAssistantCalendarService("", "", "")
        query = parse_calendar_query("/agenda", now=NOW)
        assert query is not None

        with self.assertRaises(CalendarServiceError):
            await service.events(query)

    async def test_creates_event_through_google_action(self) -> None:
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["payload"] = request.content.decode()
            return httpx.Response(200, json=[])

        service = HomeAssistantCalendarService(
            "http://homeassistant.local:8123",
            "secreto",
            "calendar.familia_millan_romero",
            transport=httpx.MockTransport(handler),
        )
        draft = parse_calendar_event_draft(
            "Añade al calendario familiar Dentista mañana a las 18:00",
            now=NOW,
        )
        assert draft is not None

        await service.create_event(draft)

        self.assertIn("/api/services/google/create_event", str(captured["url"]))
        self.assertIn("calendar.familia_millan_romero", str(captured["payload"]))
        self.assertIn("Dentista", str(captured["payload"]))


if __name__ == "__main__":
    unittest.main()
