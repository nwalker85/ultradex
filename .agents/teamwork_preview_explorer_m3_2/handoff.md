# Technical Design & Specification: Google Calendar, Sovereign Voice/Gjallarhorn & Obsidian Exporter (M3.2)

## 1. Observation

### 1.1 Context & Scope
- **Project**: Career Command Center (CCC) Job-Search CRM and Operating System
- **Working Directory**: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req`
- **Milestone Scope**: M3.2 — Google Calendar Integration & Slot Sensing (`core/jobsearch_calendar.py`), Sovereign Voice Engine & Interview Debriefs (`core/jobsearch_gjallarhorn.py`), and Obsidian Note Exporter.

### 1.2 Existing Codebase Patterns Observed
1. **Google OAuth & Authentication (`core/jobsearch_gmail.py:134-187`)**:
   - Uses `GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"` for short-lived access token renewal using refresh tokens.
   - Priority token resolution: direct access token via `GOOGLE_CALENDAR_ACCESS_TOKEN` / `GOOGLE_ACCESS_TOKEN` / `GMAIL_ACCESS_TOKEN`, falling back to `refresh_access_token` with `client_id`, `client_secret`, and `refresh_token` stored in environment variables (derived from 1Password item `op://ravenmask/Gmail OAuth - CCC Sense` or calendar-specific entries).
2. **Database Models & State Projections (`core/jobsearch_models.py`, `core/models.py`)**:
   - `OpportunityProjectionDB` (`jobsearch_opportunities`): tracks employer name, role title, state, score, risk flags, evidence refs.
   - `ApplicationProjectionDB` (`jobsearch_applications`): tracks stage history, next action, next action deadline.
   - `OrganizationDB` (`jobsearch_organizations`): aggregates contacts and leads.
   - `ContactDB` (`contacts`): includes `communication_history` JSON, `advocacy_score`, `organization_id`.
3. **Sovereign Infrastructure Topology (`~/.claude/projects/-Users-nate/memory/05-services/gjallarhorn.md`)**:
   - Sovereign ASR service running faster-whisper on `http://ratatoskr:18099/asr` (whole-file and batch chunk transcription).
   - Mosquitto MQTT message broker on `ratatoskr:1883` handling event broadcasting and transcript streaming.
4. **Obsidian Vault Standard (`PROJECT.md §F9`, `ORIGINAL_REQUEST.md §R4`)**:
   - Authoritative interview notes destination: `~/docs/40-personal/interviews/YYYY-MM-DD_<company>_<role>_debrief.md`.

---

## 2. Logic Chain

### 2.1 Technical Specification for `core/jobsearch_calendar.py`

#### 2.1.1 Architecture & Core Responsibilities
`core/jobsearch_calendar.py` is responsible for:
1. **Google Calendar v3 API Client & Event Sensing**: Fetching calendar events over specified time windows, filtering by status, handling all-day vs. timed events, and parsing transparency/free-busy status.
2. **Interview Round Detection**: Deterministically identifying scheduled interviews from event summaries, descriptions, attendee emails, and meeting links, matching against CRM employers and categorizing round types.
3. **Working Hours Availability Calculation**: Computing open, non-overlapping 30-minute and 45-minute slots strictly within Central Time working hours (09:00–17:00 CT, Monday–Friday), taking into account busy events and configurable buffer intervals (default 15 minutes).
4. **Recruiter Reply Formatting**: Formatting availability blocks in clear, human-readable Central Time layouts ready for direct insertion into Copilot 3-pill recruiter response templates.

#### 2.1.2 Data Types and Schema
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
import re
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field as PydanticField

CENTRAL_TZ = ZoneInfo("America/Chicago")
WORKING_HOURS_START = time(9, 0)   # 09:00 CT
WORKING_HOURS_END = time(17, 0)    # 17:00 CT
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

class CalendarEventStatus(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"

class CalendarTransparency(str, Enum):
    OPAQUE = "opaque"       # Busy
    TRANSPARENT = "transparent" # Free

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
```

#### 2.1.3 Algorithm: Working Hours Slot Calculation
The slot calculation algorithm operates as follows:
1. **Target Window & Day Filtering**:
   - Iterate through each calendar day from `start_date` to `end_date`.
   - Skip weekends (Saturday: `weekday() == 5`, Sunday: `weekday() == 6`).
2. **Day Boundary Definition**:
   - Construct day working bounds: `day_start = datetime.combine(current_day, time(9, 0), tzinfo=CENTRAL_TZ)` and `day_end = datetime.combine(current_day, time(17, 0), tzinfo=CENTRAL_TZ)`.
3. **Busy Interval Normalization & Buffering**:
   - For all `CalendarEvent` objects that overlap the day and have `is_busy == True`:
     * Convert start/end to `CENTRAL_TZ`.
     * Apply pre-buffer and post-buffer: `busy_start = max(day_start, event.start - timedelta(minutes=buffer_minutes))` and `busy_end = min(day_end, event.end + timedelta(minutes=buffer_minutes))`.
     * Handle all-day events: block `[day_start, day_end]`.
   - Sort busy intervals by start time and merge any overlapping or contiguous intervals.
4. **Free Interval Extraction**:
   - Compute the complement of merged busy intervals against `[day_start, day_end]`.
   - Produces a list of continuous free blocks `[(block_start_i, block_end_i)]`.
5. **Slot Generation**:
   - For a given duration `D` (e.g. 30 min, 45 min) and grid step `S` (default: 15 min or 30 min):
   - For each free block `[block_start, block_end]`:
     * Candidate slot start $T = \text{block\_start}$ (aligned to nearest standard step).
     * While $T + \text{timedelta}(minutes=D) \le \text{block\_end}$:
       - Yield `TimeSlot(start=T, end=T + D, duration_minutes=D)`.
       - Increment $T \mathrel{+}= \text{step\_minutes}$ (e.g., 30 min or 15 min).

#### 2.1.4 Availability Formatter for Recruiter Emails
Generates structured text blocks matching recruiter response expectations:
```python
def format_availability_for_recruiter(
    slots: Sequence[TimeSlot],
    style: str = "grouped_days",
    timezone_label: str = "CT"
) -> str:
    """Formats open slots into natural recruiter email copy."""
    # Style: grouped_days
    # Example Output:
    # "Here is my current availability for a 30-minute conversation (Central Time):
    #  - Tuesday, Aug 25: 09:00 AM – 11:30 AM CT, 01:30 PM – 04:00 PM CT
    #  - Wednesday, Aug 26: 10:00 AM – 12:00 PM CT, 02:00 PM – 05:00 PM CT
    #  - Thursday, Aug 27: 09:00 AM – 01:00 PM CT
    #  Please let me know if any of these windows work for your team."
```

---

### 2.2 Technical Specification for `core/jobsearch_gjallarhorn.py`

#### 2.2.1 Architecture & Component Design
`core/jobsearch_gjallarhorn.py` provides the complete Sovereign Voice pipeline:
1. **MQTT Event Listener & Client**: Connects to Mosquitto on `ratatoskr:1883`, listening for interview control signals (`gjallarhorn/interview/session`) and real-time transcript deltas (`gjallarhorn/interview/transcript`).
2. **Gjallarhorn ASR Ingestion Client**: Submits recorded audio payloads to `http://ratatoskr:18099/asr`, receiving timestamped Whisper recognition segments with speaker diarization.
3. **Structured Debrief Extraction Engine**: Synthesizes transcript into 4 structured sections:
   - **Executive Summary**: 2-3 paragraph overview of the discussion, role scope, and candidate positioning.
   - **Questions Asked & Answers Given**: Comprehensive list of technical, architectural, leadership, and culture questions with candidate answer highlights and key metrics cited.
   - **Technical & Culture Fit Assessment**: Tech stack alignment, team velocity, leadership scope, comp compatibility against $180k/$250k bounds, green flags, and explicit red flags.
   - **Action Items**: Concrete follow-up tasks (thank-you notes, technical artifacts/references, recruiter follow-ups) with SLAs.
4. **Copilot Action Injection**: Automatically converts debrief action items into `NextBestAction` recommendations on the Command Home (`/`) rail.
5. **Obsidian Markdown Note Exporter**: Formats notes with complete YAML frontmatter and writes atomically to `~/docs/40-personal/interviews/YYYY-MM-DD_<company>_<role>_debrief.md`.

#### 2.2.2 Data Models & Schemas
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence
from pydantic import BaseModel, Field as PydanticField

DEFAULT_MOSQUITTO_HOST = "ratatoskr"
DEFAULT_MOSQUITTO_PORT = 1883
DEFAULT_GJALLARHORN_ASR_URL = "http://ratatoskr:18099/asr"
DEFAULT_OBSIDIAN_VAULT_DIR = Path.home() / "docs" / "40-personal" / "interviews"

class SpeakerRole(str, Enum):
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    RECRUITER = "recruiter"
    UNKNOWN = "unknown"

class TranscriptSegment(BaseModel):
    offset_ms: int
    speaker: str
    role: SpeakerRole = SpeakerRole.UNKNOWN
    text: str
    confidence: float = 1.0

class InterviewMetadata(BaseModel):
    company: str
    role: str
    round_type: str = "Technical Deep Dive"
    interview_date: str
    interviewer_names: List[str] = PydanticField(default_factory=list)
    interviewer_titles: List[str] = PydanticField(default_factory=list)
    duration_minutes: int = 45
    audio_ref: Optional[str] = None
    opportunity_id: Optional[str] = None
    contact_ids: List[str] = PydanticField(default_factory=list)

class QuestionAnswerPair(BaseModel):
    id: str
    question: str
    asked_by: str = "interviewer"
    category: str = "technical_deep_dive"
    answer_summary: str
    key_points_mentioned: List[str] = PydanticField(default_factory=list)
    effectiveness_score: float = 9.0
    follow_up_needed: bool = False

class FitAssessment(BaseModel):
    overall_score: float = 85.0
    technical_alignment: str
    leadership_alignment: str
    compensation_alignment: str
    green_flags: List[str] = PydanticField(default_factory=list)
    red_flags: List[str] = PydanticField(default_factory=list)
    culture_notes: str = ""
    recommendation: str = "Advance"

class InterviewActionItem(BaseModel):
    id: str
    title: str
    action_type: str  # "thank_you_note", "technical_deliverable", "recruiter_follow_up"
    priority: str = "p0" # "p0", "p1", "p2"
    due_date: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    draft_content: Optional[str] = None
    opportunity_id: Optional[str] = None
    is_completed: bool = False

class InterviewDebrief(BaseModel):
    id: str
    created_at: datetime
    metadata: InterviewMetadata
    executive_summary: str
    questions_and_answers: List[QuestionAnswerPair] = PydanticField(default_factory=list)
    fit_assessment: FitAssessment
    action_items: List[InterviewActionItem] = PydanticField(default_factory=list)
    raw_transcript: str = ""
    transcript_segments: List[TranscriptSegment] = PydanticField(default_factory=list)
```

#### 2.2.3 Extraction Logic & Copilot Integration
1. **Deterministic & LLM Extraction**:
   - `extract_interview_debrief(transcript: str, metadata: InterviewMetadata) -> InterviewDebrief`:
   - Parses conversational turns using regex and prompt/parser rules.
   - Extracts questions based on interrogative structure and interviewer turns.
   - Maps Nate Walker's answers to skills taxonomy (e.g., Kubernetes, Python, Distributed Systems, ML Infrastructure).
   - Flags negative comp indicators (e.g. mentions of $<180k budget) or tech red flags (e.g., lack of automated testing).
   - Generates action items with explicit due dates:
     * Thank-you notes: `interview_date + 24 hours` (Priority: P0).
     * Technical deliverable: `interview_date + 48 hours` (Priority: P1).
2. **Copilot Action Injection**:
   - Converts each `InterviewActionItem` into a `NextBestAction`:
     ```python
     NextBestAction(
         id=f"nba-{item.id}",
         priority=1 if item.priority == "p0" else 2,
         category="interview_follow_up",
         title=item.title,
         description=f"Send thank-you email to {item.recipient_name} ({item.recipient_email}) for {debrief.metadata.company} {debrief.metadata.round_type}.",
         action_type="send_email",
         target_entity_type="opportunity",
         target_entity_id=debrief.metadata.opportunity_id,
         due_date=item.due_date,
         suggested_payload={"draft": item.draft_content, "to": item.recipient_email}
     )
     ```

#### 2.2.4 Obsidian Markdown Exporter
Writes formatted notes to `~/docs/40-personal/interviews/YYYY-MM-DD_<company>_<role>_debrief.md`.
```markdown
---
title: "Interview Debrief: Anthropic — Chief of Staff / CTO Office"
date: 2026-08-25
company: "Anthropic"
role: "Chief of Staff / CTO Office"
round: "Technical Deep Dive"
interviewers:
  - "Sarah Chen (Director of Eng)"
fit_score: 92.0
status: completed
tags:
  - interview
  - debrief
  - jobsearch
  - anthropic
---

# Interview Debrief: Anthropic — Chief of Staff / CTO Office

**Date**: 2026-08-25  
**Round**: Technical Deep Dive  
**Interviewers**: Sarah Chen (Director of Eng)  
**Fit Score**: 92.0 / 100  

## Executive Summary
In-depth 45-minute discussion focusing on high-throughput model serving architecture, agent coordination loops, and developer tooling infrastructure. Strong cultural and architectural alignment with Anthropic's safety and scalability roadmap.

## Questions Asked & Answers Given
### 1. How do you approach zero-downtime database migrations on large-scale distributed systems?
- **Category**: Distributed Systems / Architecture
- **Answer Summary**: Described expand/contract pattern using Alembic, dual-writing with shadow reads, and verifying invariants before dropping columns.
- **Effectiveness**: 9.5 / 10

## Technical & Culture Fit Assessment
- **Technical Alignment**: Exceptional overlap with Python, FastAPI, K8s, and event-driven architectures.
- **Leadership Alignment**: Clear resonance with Nate's pragmatic engineering stewardship.
- **Compensation Alignment**: Budget aligns with $180k base / $250k target expectation.

### Green Flags & Highlights
- High team velocity with strong emphasis on type safety and automated testing.
- Modern infrastructure stack (k8s, NATS, FastAPI).

### Red Flags & Risks
- Fast-evolving requirements may require frequent context switching.

## Action Items & Next Steps
- [ ] **P0 (Due 2026-08-26)**: Send thank-you note to Sarah Chen referencing the migration discussion.
- [ ] **P1 (Due 2026-08-27)**: Share repository link for the open-source event-sourcing harness.

## Raw Transcript
[00:00:05] **Interviewer**: Welcome Nate, great to meet you...
```

---

## 3. Caveats

1. **Google OAuth Token Refresh Seam**:
   - Google Calendar v3 API requires network connectivity to `oauth2.googleapis.com` for token refresh. In offline or unit-test environments, a mock client or local test harness MUST be provided.
2. **Mosquitto & Gjallarhorn Network Seam**:
   - `ratatoskr:1883` and `ratatoskr:18099` are internal Ravenhelm hostnames. Test suites must mock socket/HTTP connections or provide an in-memory loopback to ensure 100% test reliability in isolated CI/dev environments.
3. **Timezone Authority**:
   - All calendar slot math MUST use `America/Chicago` (Central Time) explicitly to avoid UTC-offset skew or Daylight Saving Time transition errors.
4. **Obsidian Path Sandboxing**:
   - The Obsidian exporter defaults to `~/docs/40-personal/interviews/` but must accept a configurable directory parameter (`vault_dir: Path`) to enable isolated temp directory testing without touching production documents.

---

## 4. Conclusion

The designs for `core/jobsearch_calendar.py` and `core/jobsearch_gjallarhorn.py` provide a clean, complete, and robust implementation plan for Milestone M3.2.
- `jobsearch_calendar.py` cleanly integrates Google Calendar API sensing, Central Time working hours (09:00–17:00 CT) open slot calculations for 30-min and 45-min durations with buffer math, and recruiter response text formatting.
- `jobsearch_gjallarhorn.py` cleanly provides the MQTT and ASR sovereign voice pipeline, structured interview debrief extraction, Copilot Next Best Action auto-injection, and atomic Obsidian note exporting.

---

## 5. Verification Method

### 5.1 Test Plan for `tests/test_jobsearch_calendar.py`
The test suite will verify:
1. `test_resolve_calendar_access_token`: Direct env token, OAuth refresh flow, error handling for missing/invalid credentials.
2. `test_fetch_calendar_events`: Mock HTTP calls to Google Calendar v3 API, pagination, time bounds (`timeMin`, `timeMax`), event parsing.
3. `test_detect_interview_rounds`: Keyword parsing (`interview`, `screen`, `system design`), organizer matching against CRM companies, video link extraction.
4. `test_working_hours_slot_calculation_clean_day`: Computes all open 30-min and 45-min slots on a clean weekday (09:00–17:00 CT = 16 30-min slots, 10 45-min slots).
5. `test_working_hours_slot_calculation_busy_events_with_buffer`: Tests blocking of overlapping busy events and 15-min pre/post buffer intervals.
6. `test_working_hours_slot_calculation_all_day_event`: Confirms all-day busy events eliminate all slots for that day.
7. `test_working_hours_slot_calculation_weekends`: Confirms Saturday and Sunday return zero slots.
8. `test_working_hours_slot_calculation_dst_transitions`: Verifies stability during Daylight Saving Time boundaries (CDT/CST).
9. `test_format_availability_for_recruiter`: Validates formatted recruiter email copy across different styles (`grouped_days`, `slot_list`, `compact`).

### 5.2 Test Plan for `tests/test_jobsearch_gjallarhorn.py`
The test suite will verify:
1. `test_gjallarhorn_asr_client_transcribe`: Mock HTTP POST to `http://ratatoskr:18099/asr`, validates segment parsing, timestamps, and confidence scores.
2. `test_mqtt_listener_transcript_accumulation`: Simulates MQTT stream packets on `gjallarhorn/interview/transcript` and verifies chronological transcript reassembly.
3. `test_extract_interview_debrief_structured`: Verifies extraction of Executive Summary, Questions & Answers, Fit Assessment, Red/Green Flags, and Action Items from a realistic interview transcript.
4. `test_debrief_action_items_copilot_injection`: Asserts conversion of interview action items (thank-you notes, deliverables) into Copilot `NextBestAction` models with priority and 24h SLA.
5. `test_obsidian_exporter_writes_valid_markdown`: Exports debrief to a temporary directory, parses YAML frontmatter, headings, checkboxes, and content.
6. `test_obsidian_exporter_filename_sanitization`: Verifies special characters, slashes, and spaces in company/role names are sanitized cleanly.
7. `test_obsidian_exporter_idempotent_atomic_overwrite`: Validates atomic file writing and overwriting without file corruption.

### 5.3 Execution Command
```bash
pytest tests/test_jobsearch_calendar.py tests/test_jobsearch_gjallarhorn.py -v
```
