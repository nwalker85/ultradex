"""Tests for Google Calendar Integration & Slot Sensing Engine (Milestone M3, Feature F8)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest
import httpx
from zoneinfo import ZoneInfo

from core.jobsearch_calendar import (
    CENTRAL_TZ,
    CalendarEvent,
    CalendarEventStatus,
    CalendarTransparency,
    GoogleCalendarClient,
    InterviewRoundType,
    TimeSlot,
    compute_daily_availability,
    compute_open_slots,
    format_availability_for_recruiter,
    get_open_working_hour_slots,
    resolve_calendar_access_token,
)
from core.jobsearch_gmail import GmailAuthError


def test_resolve_calendar_access_token_direct_env() -> None:
    token = resolve_calendar_access_token(
        environ={"GOOGLE_CALENDAR_ACCESS_TOKEN": "direct-cal-token-123"}
    )
    assert token == "direct-cal-token-123"

    token_gmail = resolve_calendar_access_token(
        environ={"GMAIL_ACCESS_TOKEN": "direct-gmail-token-456"}
    )
    assert token_gmail == "direct-gmail-token-456"


def test_resolve_calendar_access_token_missing_raises_error() -> None:
    with pytest.raises(GmailAuthError) as exc:
        resolve_calendar_access_token(environ={})
    assert "calendar_credentials_missing" in str(exc.value)


def test_resolve_calendar_access_token_oauth_refresh() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://oauth2.googleapis.com/token"
        return httpx.Response(200, json={"access_token": "refreshed-cal-token-789"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        token = resolve_calendar_access_token(
            environ={
                "GOOGLE_CLIENT_ID": "cid",
                "GOOGLE_CLIENT_SECRET": "csec",
                "GOOGLE_REFRESH_TOKEN": "rtok",
            },
            client=mock_http,
        )
    assert token == "refreshed-cal-token-789"


def test_fetch_calendar_events_parsing() -> None:
    mock_payload = {
        "items": [
            {
                "id": "event-1",
                "summary": "Recruiter Screen with Anthropic",
                "description": "Zoom link: https://anthropic.zoom.us/j/987654321",
                "start": {"dateTime": "2026-08-25T15:00:00Z"},
                "end": {"dateTime": "2026-08-25T15:45:00Z"},
                "status": "confirmed",
                "transparency": "opaque",
                "attendees": [{"email": "recruiter@anthropic.com"}, {"email": "nate@theviking.ai"}],
            },
            {
                "id": "event-2",
                "summary": "Vacation Day",
                "start": {"date": "2026-08-26"},
                "end": {"date": "2026-08-26"},
                "status": "confirmed",
                "transparency": "opaque",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_payload)

    client = GoogleCalendarClient()
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        events = client.fetch_events(
            access_token="tok",
            time_min=datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc),
            time_max=datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc),
            client=mock_http,
        )

    assert len(events) == 2
    ev1 = events[0]
    assert ev1.id == "event-1"
    assert ev1.summary == "Recruiter Screen with Anthropic"
    assert ev1.is_busy is True
    assert ev1.meeting_link == "https://anthropic.zoom.us/j/987654321"
    assert "recruiter@anthropic.com" in ev1.attendees

    ev2 = events[1]
    assert ev2.id == "event-2"
    assert ev2.is_all_day is True
    assert ev2.is_busy is True


def test_detect_interview_rounds() -> None:
    client = GoogleCalendarClient()
    events = [
        CalendarEvent(
            id="ev-1",
            summary="Recruiter Screen with Anthropic",
            description="Discussing Head of AI role",
            start=datetime(2026, 8, 25, 10, 0, tzinfo=CENTRAL_TZ),
            end=datetime(2026, 8, 25, 10, 30, tzinfo=CENTRAL_TZ),
            meeting_link="https://anthropic.zoom.us/j/123",
            attendees=["sarah@anthropic.com"],
        ),
        CalendarEvent(
            id="ev-2",
            summary="System Design Interview with OpenAI",
            description="Distributed ML Architecture",
            start=datetime(2026, 8, 26, 14, 0, tzinfo=CENTRAL_TZ),
            end=datetime(2026, 8, 26, 15, 0, tzinfo=CENTRAL_TZ),
            meeting_link="https://meet.google.com/abc-def-ghi",
            attendees=["eng-lead@openai.com"],
        ),
        CalendarEvent(
            id="ev-3",
            summary="Dentist Appointment",
            start=datetime(2026, 8, 27, 9, 0, tzinfo=CENTRAL_TZ),
            end=datetime(2026, 8, 27, 10, 0, tzinfo=CENTRAL_TZ),
        ),
    ]

    rounds = client.detect_interview_rounds(events=events, target_companies=["Anthropic", "OpenAI"])
    assert len(rounds) == 2

    r1 = rounds[0]
    assert r1.company_name == "Anthropic"
    assert r1.round_type == InterviewRoundType.RECRUITER_SCREEN
    assert r1.confidence_score >= 0.8
    assert "Sarah" in r1.interviewer_names

    r2 = rounds[1]
    assert r2.company_name == "OpenAI"
    assert r2.round_type == InterviewRoundType.SYSTEM_DESIGN


def test_working_hours_slot_calculation_clean_day() -> None:
    # Tuesday Aug 25, 2026: 09:00–17:00 CT (8 hours = 480 minutes)
    clean_day = date(2026, 8, 25)

    # 30-min slots, 30-min step -> 16 slots (09:00, 09:30, ..., 16:30)
    slots_30 = compute_open_slots(
        events=[],
        start_date=clean_day,
        end_date=clean_day,
        duration_minutes=30,
        step_minutes=30,
    )
    assert len(slots_30) == 16
    assert slots_30[0].formatted_ct == "9:00 AM – 9:30 AM CT"
    assert slots_30[-1].formatted_ct == "4:30 PM – 5:00 PM CT"

    # 45-min slots, 45-min step -> (8 * 60) // 45 = 10 slots
    slots_45 = compute_open_slots(
        events=[],
        start_date=clean_day,
        end_date=clean_day,
        duration_minutes=45,
        step_minutes=45,
    )
    assert len(slots_45) == 10
    assert slots_45[0].formatted_ct == "9:00 AM – 9:45 AM CT"


def test_working_hours_slot_calculation_busy_events_with_buffer() -> None:
    target_day = date(2026, 8, 25)

    # Busy meeting 10:00 to 11:00 CT
    # With 15 min buffer -> blocked from 09:45 to 11:15 CT
    busy_event = CalendarEvent(
        id="busy-1",
        summary="Architecture Sync",
        start=datetime(2026, 8, 25, 10, 0, tzinfo=CENTRAL_TZ),
        end=datetime(2026, 8, 25, 11, 0, tzinfo=CENTRAL_TZ),
        status=CalendarEventStatus.CONFIRMED,
        transparency=CalendarTransparency.OPAQUE,
    )

    slots = compute_open_slots(
        events=[busy_event],
        start_date=target_day,
        end_date=target_day,
        duration_minutes=30,
        step_minutes=30,
        buffer_minutes=15,
    )

    # 09:00–09:30 is in free window [09:00, 09:45] -> valid
    # 09:30–10:00 would end at 10:00 > 09:45 -> excluded
    # [11:15, 17:00] -> first 30-min slot is 11:15–11:45
    formatted_list = [s.formatted_ct for s in slots]
    assert "9:00 AM – 9:30 AM CT" in formatted_list
    assert "9:30 AM – 10:00 AM CT" not in formatted_list
    assert "10:00 AM – 10:30 AM CT" not in formatted_list
    assert "10:30 AM – 11:00 AM CT" not in formatted_list


def test_working_hours_slot_calculation_all_day_event() -> None:
    target_day = date(2026, 8, 26)  # Wednesday
    all_day_event = CalendarEvent(
        id="allday-1",
        summary="All Day Summit",
        start=datetime(2026, 8, 26, 0, 0, tzinfo=CENTRAL_TZ),
        end=datetime(2026, 8, 26, 23, 59, tzinfo=CENTRAL_TZ),
        is_all_day=True,
        status=CalendarEventStatus.CONFIRMED,
        transparency=CalendarTransparency.OPAQUE,
    )

    slots = compute_open_slots(
        events=[all_day_event],
        start_date=target_day,
        end_date=target_day,
        duration_minutes=30,
    )
    assert len(slots) == 0


def test_working_hours_slot_calculation_weekends() -> None:
    # Aug 29 = Saturday, Aug 30 = Sunday, 2026
    saturday = date(2026, 8, 29)
    sunday = date(2026, 8, 30)

    slots = compute_open_slots(
        events=[],
        start_date=saturday,
        end_date=sunday,
        duration_minutes=30,
    )
    assert len(slots) == 0


def test_daily_availability_computation() -> None:
    start_d = date(2026, 8, 24)  # Monday
    end_d = date(2026, 8, 25)    # Tuesday

    daily = compute_daily_availability(
        events=[],
        start_date=start_d,
        end_date=end_d,
    )
    assert len(daily) == 2
    assert daily[0].day_name == "Monday"
    assert len(daily[0].slots_30min) == 16
    assert len(daily[0].slots_45min) == 10
    assert daily[1].day_name == "Tuesday"


def test_format_availability_for_recruiter() -> None:
    day = date(2026, 8, 25)
    slots = [
        TimeSlot(
            start=datetime(2026, 8, 25, 9, 0, tzinfo=CENTRAL_TZ),
            end=datetime(2026, 8, 25, 9, 30, tzinfo=CENTRAL_TZ),
            duration_minutes=30,
            day_key="2026-08-25",
            formatted_ct="9:00 AM – 9:30 AM CT",
        ),
        TimeSlot(
            start=datetime(2026, 8, 25, 14, 0, tzinfo=CENTRAL_TZ),
            end=datetime(2026, 8, 25, 14, 30, tzinfo=CENTRAL_TZ),
            duration_minutes=30,
            day_key="2026-08-25",
            formatted_ct="2:00 PM – 2:30 PM CT",
        ),
    ]

    formatted_grouped = format_availability_for_recruiter(slots, style="grouped_days")
    assert "Tuesday, Aug 25: 9:00 AM – 9:30 AM CT, 2:00 PM – 2:30 PM CT" in formatted_grouped

    formatted_compact = format_availability_for_recruiter(slots, style="compact")
    assert "• Tuesday, Aug 25 (9:00 AM – 9:30 AM CT, 2:00 PM – 2:30 PM CT)" in formatted_compact

    # Empty slots fallback
    empty_formatted = format_availability_for_recruiter([], style="grouped_days")
    assert "I am flexible this week between 9:00 AM and 5:00 PM CT" in empty_formatted
