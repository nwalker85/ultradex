"""Google Calendar Integration & Slot Sensing Engine (Milestone M3, Feature F8).

Provides Google Calendar v3 API sensing, interview round detection, Central Time
working hours (09:00–17:00 CT) open slot calculations for 30-min and 45-min slots
with busy event buffers, and recruiter response availability formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
import os
import re
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field as PydanticField

from core.jobsearch_gmail import (
    GOOGLE_TOKEN_URL,
    GmailAuthError,
    refresh_access_token,
)

CENTRAL_TZ = ZoneInfo("America/Chicago")
WORKING_HOURS_START = time(9, 0)  # 09:00 CT
WORKING_HOURS_END = time(17, 0)   # 17:00 CT
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class CalendarEventStatus(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class CalendarTransparency(str, Enum):
    OPAQUE = "opaque"          # Busy
    TRANSPARENT = "transparent"  # Free


class InterviewRoundType(str, Enum):
    RECRUITER_SCREEN = "recruiter_screen"
    HIRING_MANAGER_SCREEN = "hiring_manager_screen"
    TECHNICAL_DEEP_DIVE = "technical_deep_dive"
    SYSTEM_DESIGN = "system_design"
    CODING_ARCHITECTURE = "coding_architecture"
    EXECUTIVE_CULTURE = "executive_culture"
    ONSITE_LOOP = "onsite_loop"
    OFFER_REVIEW = "offer_review"
    UNKNOWN = "unknown"


class CalendarEvent(BaseModel):
    id: str
    summary: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    is_all_day: bool = False
    status: CalendarEventStatus = CalendarEventStatus.CONFIRMED
    transparency: CalendarTransparency = CalendarTransparency.OPAQUE
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    attendees: List[str] = PydanticField(default_factory=list)
    organizer_email: Optional[str] = None

    @property
    def is_busy(self) -> bool:
        return (
            self.status != CalendarEventStatus.CANCELLED
            and self.transparency == CalendarTransparency.OPAQUE
        )


class DetectedInterviewRound(BaseModel):
    event_id: str
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    round_type: InterviewRoundType
    confidence_score: float
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    interviewer_names: List[str] = PydanticField(default_factory=list)
    interviewer_emails: List[str] = PydanticField(default_factory=list)
    matched_keywords: List[str] = PydanticField(default_factory=list)


class TimeSlot(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int
    day_key: str
    formatted_ct: str


class DailyAvailability(BaseModel):
    date_str: str
    day_name: str
    slots_30min: List[TimeSlot] = PydanticField(default_factory=list)
    slots_45min: List[TimeSlot] = PydanticField(default_factory=list)
    busy_intervals: List[Tuple[datetime, datetime]] = PydanticField(default_factory=list)


def _to_central(dt: datetime) -> datetime:
    """Converts naive or timezone-aware datetime to America/Chicago."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(CENTRAL_TZ)
    return dt.astimezone(CENTRAL_TZ)


def resolve_calendar_access_token(
    *,
    environ: Optional[MutableMapping[str, str]] = None,
    client: Optional[httpx.Client] = None,
) -> str:
    """Resolves access token for Google Calendar API from environment or OAuth refresh."""
    env = environ if environ is not None else os.environ

    direct = (
        env.get("GOOGLE_CALENDAR_ACCESS_TOKEN")
        or env.get("GOOGLE_ACCESS_TOKEN")
        or env.get("GMAIL_ACCESS_TOKEN")
        or ""
    ).strip()
    if direct:
        return direct

    client_id = (env.get("GOOGLE_CLIENT_ID") or env.get("GMAIL_CLIENT_ID") or "").strip()
    client_secret = (
        env.get("GOOGLE_CLIENT_SECRET") or env.get("GMAIL_CLIENT_SECRET") or ""
    ).strip()
    refresh_token = (
        env.get("GOOGLE_CALENDAR_REFRESH_TOKEN")
        or env.get("GOOGLE_REFRESH_TOKEN")
        or env.get("GMAIL_REFRESH_TOKEN")
        or ""
    ).strip()

    if not (client_id and client_secret and refresh_token):
        raise GmailAuthError("calendar_credentials_missing")

    def _do_refresh(c: httpx.Client) -> str:
        return refresh_access_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            client=c,
        )

    if client:
        return _do_refresh(client)
    with httpx.Client() as sync_c:
        return _do_refresh(sync_c)


class GoogleCalendarClient:
    """Client for Google Calendar v3 API and event sensing."""

    def __init__(
        self,
        api_base: str = GOOGLE_CALENDAR_EVENTS_URL,
    ) -> None:
        self.api_base = api_base

    def parse_event_payload(self, item: Dict[str, Any]) -> CalendarEvent:
        """Parses a Google Calendar v3 API event item into CalendarEvent model."""
        event_id = item.get("id", "")
        summary = item.get("summary", "")
        description = item.get("description")
        location = item.get("location")

        # Parse start
        start_dict = item.get("start", {})
        if "dateTime" in start_dict:
            is_all_day = False
            start_dt = _to_central(
                datetime.fromisoformat(start_dict["dateTime"].replace("Z", "+00:00"))
            )
        elif "date" in start_dict:
            is_all_day = True
            d = date.fromisoformat(start_dict["date"])
            start_dt = datetime(d.year, d.month, d.day, 0, 0, tzinfo=CENTRAL_TZ)
        else:
            is_all_day = False
            start_dt = datetime.now(CENTRAL_TZ)

        # Parse end
        end_dict = item.get("end", {})
        if "dateTime" in end_dict:
            end_dt = _to_central(
                datetime.fromisoformat(end_dict["dateTime"].replace("Z", "+00:00"))
            )
        elif "date" in end_dict:
            d = date.fromisoformat(end_dict["date"])
            end_dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=CENTRAL_TZ)
        else:
            end_dt = start_dt + timedelta(minutes=30)

        # Status & Transparency
        raw_status = item.get("status", "confirmed").lower()
        status = (
            CalendarEventStatus(raw_status)
            if raw_status in [e.value for e in CalendarEventStatus]
            else CalendarEventStatus.CONFIRMED
        )

        raw_trans = item.get("transparency", "opaque").lower()
        transparency = (
            CalendarTransparency(raw_trans)
            if raw_trans in [e.value for e in CalendarTransparency]
            else CalendarTransparency.OPAQUE
        )

        # Attendees
        attendees = [
            att.get("email", "") for att in item.get("attendees", []) if att.get("email")
        ]
        organizer = item.get("organizer", {}).get("email")

        # Meeting link
        meeting_link = None
        hangout = item.get("hangoutLink")
        if hangout:
            meeting_link = hangout
        else:
            conf_data = item.get("conferenceData", {})
            for entry_point in conf_data.get("entryPoints", []):
                uri = entry_point.get("uri")
                if uri:
                    meeting_link = uri
                    break

        if not meeting_link and description:
            m_zoom = re.search(r"https://[a-zA-Z0-9.-]*zoom\.us/j/[0-9a-zA-Z?=&_]+", description)
            if m_zoom:
                meeting_link = m_zoom.group(0)
            else:
                m_meet = re.search(r"https://meet\.google\.com/[a-z0-9-]+", description)
                if m_meet:
                    meeting_link = m_meet.group(0)

        return CalendarEvent(
            id=event_id,
            summary=summary,
            description=description,
            start=start_dt,
            end=end_dt,
            is_all_day=is_all_day,
            status=status,
            transparency=transparency,
            location=location,
            meeting_link=meeting_link,
            attendees=attendees,
            organizer_email=organizer,
        )

    def fetch_events(
        self,
        access_token: str,
        time_min: datetime,
        time_max: datetime,
        client: Optional[httpx.Client] = None,
    ) -> List[CalendarEvent]:
        """Fetches calendar events from Google Calendar v3 API within [time_min, time_max]."""
        params: Dict[str, Any] = {
            "timeMin": time_min.astimezone(timezone.utc).isoformat(),
            "timeMax": time_max.astimezone(timezone.utc).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        def _do_get(c: httpx.Client) -> httpx.Response:
            return c.get(self.api_base, params=params, headers=headers, timeout=20.0)

        if client:
            resp = _do_get(client)
        else:
            with httpx.Client() as sync_c:
                resp = _do_get(sync_c)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Google Calendar API fetch failed with HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        items = data.get("items", [])
        return [self.parse_event_payload(item) for item in items]

    def detect_interview_rounds(
        self,
        events: Sequence[CalendarEvent],
        target_companies: Optional[Sequence[str]] = None,
    ) -> List[DetectedInterviewRound]:
        """Detects interview rounds from events based on keywords, descriptions, and attendees."""
        rounds: List[DetectedInterviewRound] = []

        round_keyword_map = [
            (
                r"(system\s+design|architecture\s+review|system\s+architecture)",
                InterviewRoundType.SYSTEM_DESIGN,
            ),
            (
                r"(technical\s+deep\s+dive|technical\s+interview|deep\s+dive|coding|algorithms|live\s+coding)",
                InterviewRoundType.TECHNICAL_DEEP_DIVE,
            ),
            (
                r"(recruiter\s+screen|introductory\s+call|initial\s+chat|talent\s+screen|phone\s+screen)",
                InterviewRoundType.RECRUITER_SCREEN,
            ),
            (
                r"(hiring\s+manager|engineering\s+leader|manager\s+chat|team\s+lead\s+screen)",
                InterviewRoundType.HIRING_MANAGER_SCREEN,
            ),
            (
                r"(executive|founder|cto\s+chat|culture\s+fit|values|behavioral)",
                InterviewRoundType.EXECUTIVE_CULTURE,
            ),
            (
                r"(onsite|virtual\s+onsite|final\s+loop|full\s+loop|superday)",
                InterviewRoundType.ONSITE_LOOP,
            ),
            (
                r"(offer\s+discussion|offer\s+call|compensation\s+review|package\s+review)",
                InterviewRoundType.OFFER_REVIEW,
            ),
        ]

        interview_broad_regex = re.compile(
            r"\b(interview|screen|chat|discussion|round|sync|loop)\b", re.IGNORECASE
        )

        for event in events:
            if event.status == CalendarEventStatus.CANCELLED:
                continue

            text_to_search = f"{event.summary} {event.description or ''}"
            matched_keywords = []

            is_interview_candidate = False
            if interview_broad_regex.search(event.summary) or (
                event.meeting_link and interview_broad_regex.search(text_to_search)
            ):
                is_interview_candidate = True

            # Match target company
            matched_company = None
            if target_companies:
                for comp in target_companies:
                    if re.search(rf"\b{re.escape(comp)}\b", text_to_search, re.IGNORECASE):
                        matched_company = comp
                        is_interview_candidate = True
                        break

            # If company in summary (e.g. "Anthropic Interview", "Chat with OpenAI")
            if not matched_company:
                m_comp = re.search(
                    r"(?:with|at|for)\s+([A-Z][A-Za-z0-9&.\s]{1,30}?)(?=[,\.\n\r\?\!]|\s+interview|$)",
                    text_to_search,
                )
                if m_comp and m_comp.group(1):
                    cand = m_comp.group(1).strip()
                    if cand.lower() not in {"the", "a", "an", "our", "my", "your", "us"}:
                        matched_company = cand

            if not is_interview_candidate and not matched_company:
                continue

            detected_round = InterviewRoundType.UNKNOWN
            for pattern, r_type in round_keyword_map:
                if re.search(pattern, text_to_search, re.IGNORECASE):
                    detected_round = r_type
                    matched_keywords.append(r_type.value)
                    break

            if detected_round == InterviewRoundType.UNKNOWN and is_interview_candidate:
                detected_round = InterviewRoundType.RECRUITER_SCREEN

            confidence = 0.9 if matched_company and detected_round != InterviewRoundType.UNKNOWN else 0.7

            interviewer_names = []
            for att in event.attendees:
                if "@" in att and not att.endswith("theviking.ai") and not att.endswith("gmail.com"):
                    local = att.split("@")[0]
                    interviewer_names.append(" ".join(p.capitalize() for p in re.split(r"[._-]", local)))

            rounds.append(
                DetectedInterviewRound(
                    event_id=event.id,
                    company_name=matched_company or "Target Employer",
                    role_title=None,
                    round_type=detected_round,
                    confidence_score=confidence,
                    start_time=event.start,
                    end_time=event.end,
                    meeting_link=event.meeting_link,
                    interviewer_names=interviewer_names,
                    interviewer_emails=[a for a in event.attendees if not a.endswith("theviking.ai")],
                    matched_keywords=matched_keywords,
                )
            )

        return rounds


def compute_open_slots(
    events: Sequence[CalendarEvent],
    start_date: date | datetime,
    end_date: date | datetime,
    duration_minutes: int = 30,
    step_minutes: int = 30,
    buffer_minutes: int = 15,
) -> List[TimeSlot]:
    """Computes open non-overlapping working hours slots (09:00–17:00 CT, Mon–Fri)."""
    s_date = start_date.date() if isinstance(start_date, datetime) else start_date
    e_date = end_date.date() if isinstance(end_date, datetime) else end_date

    slots: List[TimeSlot] = []
    curr_day = s_date

    while curr_day <= e_date:
        # Skip weekends: Saturday (5), Sunday (6)
        if curr_day.weekday() >= 5:
            curr_day += timedelta(days=1)
            continue

        day_start = datetime(curr_day.year, curr_day.month, curr_day.day, 9, 0, tzinfo=CENTRAL_TZ)
        day_end = datetime(curr_day.year, curr_day.month, curr_day.day, 17, 0, tzinfo=CENTRAL_TZ)

        busy_intervals: List[Tuple[datetime, datetime]] = []

        for ev in events:
            if not ev.is_busy:
                continue

            ev_start = _to_central(ev.start)
            ev_end = _to_central(ev.end)

            if ev.is_all_day:
                # Check if all day overlaps current day
                if ev_start.date() <= curr_day <= ev_end.date():
                    busy_intervals.append((day_start, day_end))
                continue

            # Check overlap with working window
            if ev_end <= day_start or ev_start >= day_end:
                continue

            b_start = max(day_start, ev_start - timedelta(minutes=buffer_minutes))
            b_end = min(day_end, ev_end + timedelta(minutes=buffer_minutes))
            if b_end > b_start:
                busy_intervals.append((b_start, b_end))

        # Merge overlapping/contiguous busy intervals
        busy_intervals.sort(key=lambda x: x[0])
        merged_busy: List[Tuple[datetime, datetime]] = []
        for b_start, b_end in busy_intervals:
            if not merged_busy:
                merged_busy.append((b_start, b_end))
            else:
                prev_start, prev_end = merged_busy[-1]
                if b_start <= prev_end:
                    merged_busy[-1] = (prev_start, max(prev_end, b_end))
                else:
                    merged_busy.append((b_start, b_end))

        # Compute free continuous intervals
        free_intervals: List[Tuple[datetime, datetime]] = []
        cursor = day_start
        for b_start, b_end in merged_busy:
            if b_start > cursor:
                free_intervals.append((cursor, b_start))
            cursor = max(cursor, b_end)
        if cursor < day_end:
            free_intervals.append((cursor, day_end))

        # Slice free intervals into discrete TimeSlots
        for f_start, f_end in free_intervals:
            slot_cursor = f_start
            while slot_cursor + timedelta(minutes=duration_minutes) <= f_end:
                slot_end = slot_cursor + timedelta(minutes=duration_minutes)
                day_key = slot_cursor.strftime("%Y-%m-%d")
                formatted = (
                    f"{slot_cursor.strftime('%I:%M %p').lstrip('0')} – "
                    f"{slot_end.strftime('%I:%M %p').lstrip('0')} CT"
                )
                slots.append(
                    TimeSlot(
                        start=slot_cursor,
                        end=slot_end,
                        duration_minutes=duration_minutes,
                        day_key=day_key,
                        formatted_ct=formatted,
                    )
                )
                slot_cursor += timedelta(minutes=step_minutes)

        curr_day += timedelta(days=1)

    return slots


def compute_daily_availability(
    events: Sequence[CalendarEvent],
    start_date: date | datetime,
    end_date: date | datetime,
    buffer_minutes: int = 15,
) -> List[DailyAvailability]:
    """Computes DailyAvailability summaries for 30-min and 45-min slots."""
    s_date = start_date.date() if isinstance(start_date, datetime) else start_date
    e_date = end_date.date() if isinstance(end_date, datetime) else end_date

    daily_list: List[DailyAvailability] = []
    curr_day = s_date

    while curr_day <= e_date:
        if curr_day.weekday() < 5:  # Mon-Fri
            slots_30 = compute_open_slots(
                events=events,
                start_date=curr_day,
                end_date=curr_day,
                duration_minutes=30,
                step_minutes=30,
                buffer_minutes=buffer_minutes,
            )
            slots_45 = compute_open_slots(
                events=events,
                start_date=curr_day,
                end_date=curr_day,
                duration_minutes=45,
                step_minutes=45,
                buffer_minutes=buffer_minutes,
            )
            day_dt = datetime(curr_day.year, curr_day.month, curr_day.day, tzinfo=CENTRAL_TZ)
            daily_list.append(
                DailyAvailability(
                    date_str=curr_day.strftime("%Y-%m-%d"),
                    day_name=day_dt.strftime("%A"),
                    slots_30min=slots_30,
                    slots_45min=slots_45,
                    busy_intervals=[],
                )
            )
        curr_day += timedelta(days=1)

    return daily_list


def format_availability_for_recruiter(
    slots: Sequence[TimeSlot],
    style: str = "grouped_days",
    timezone_label: str = "CT",
) -> str:
    """Formats open slots into natural recruiter email copy."""
    if not slots:
        return (
            f"I am flexible this week between 9:00 AM and 5:00 PM {timezone_label}. "
            f"Please feel free to send over a few times that work best for your team."
        )

    # Group by day
    days_map: Dict[str, List[str]] = {}
    day_order: List[str] = []

    for s in slots:
        day_label = s.start.strftime("%A, %b %d")
        if day_label not in days_map:
            days_map[day_label] = []
            day_order.append(day_label)
        days_map[day_label].append(s.formatted_ct)

    if style == "grouped_days":
        lines = []
        for day in day_order:
            times = ", ".join(days_map[day])
            lines.append(f"{day}: {times}")
        return "\n".join(lines)

    elif style == "compact":
        lines = []
        for day in day_order:
            times = ", ".join(days_map[day])
            lines.append(f"• {day} ({times})")
        return "\n".join(lines)

    else:  # slot_list
        return "\n".join(f"• {s.start.strftime('%A, %b %d')}: {s.formatted_ct}" for s in slots)


# Standalone convenience helper matching interface contracts
def get_open_working_hour_slots(
    events: Sequence[CalendarEvent],
    start_date: date | datetime,
    end_date: date | datetime,
    duration_minutes: int = 30,
    buffer_minutes: int = 15,
) -> List[TimeSlot]:
    return compute_open_slots(
        events=events,
        start_date=start_date,
        end_date=end_date,
        duration_minutes=duration_minutes,
        buffer_minutes=buffer_minutes,
    )
