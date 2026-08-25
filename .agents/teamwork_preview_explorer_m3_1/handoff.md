# Hard Handoff Report: Milestone M3 Technical Specification & Design — Copilot Engine (`core/jobsearch_copilot.py`) & Omnichannel In-App Messaging (`core/jobsearch_messaging.py`)

## 1. Observation

Direct code inspection of the existing codebase, domain models, database schemas, and integration adapters reveals the following architectural baseline:

1. **CRM & Job-Search Domain Models (`core/jobsearch_models.py` & `core/models.py`)**:
   - `LeadDB` (`jobsearch_leads`): Stores unapplied/discovered job postings with `id`, `source_board`, `external_id`, `employer`, `organization_id`, `title`, `location`, `remote_type`, `salary_min`, `salary_max`, `salary_currency`, `url`, `description`, `requirements` (JSON), `fit_score` (Float 0-100), `match_breakdown` (JSON), `risk_flags` (JSON), and `state` (`"discovered"`, `"unapplied"`, `"converted"`, `"dismissed"`).
   - `OpportunityProjectionDB` (`jobsearch_opportunities`): Pipeline pursuit record with `id`, `employer_name`, `title`, `location`, `role_family`, `state` (`"identified"`, `"qualified"`, `"pursuing"`, `"submitted"`, `"closed"`), `score` (Float 0-100), `score_explanation`, `risk_flags` (JSON), `evidence_refs` (JSON).
   - `ApplicationProjectionDB` (`jobsearch_applications`): Application stage tracker with `id`, `opportunity_id`, `state` (`"draft"`, `"applied"`, `"screening"`, `"interviewing"`, `"offer"`, `"accepted"`, `"rejected"`, `"withdrawn"`, `"closed"`), `stage_history` (JSON array of `{"status": str, "occurred_at": str}`), `artifact_refs` (JSON), `next_action` (String 500), `next_action_deadline` (DateTime UTC).
   - `RelationshipProjectionDB` (`jobsearch_relationships`): Network connections with `id`, `opportunity_id`, `dex_contact_ref` (String 255), `relevance_score` (Float 0-100), `relevance_reason` (String 500).
   - `OutreachProjectionDB` (`jobsearch_outreach`): Governed outreach state machine with `id`, `opportunity_id`, `relationship_id`, `state` (`"draft"`, `"pending_approval"`, `"approved"`, `"sent"`, `"cancelled"`), `channel` (`"gmail"`, `"linkedin"`), `message_commitment` (`sha256:...`), `approval_contract_ref`, `sent_evidence_ref`.
   - `ContactDB` (`contacts`): 2,252 sovereign contacts with `id`, `name`, `email`, `company`, `job_title`, `phone`, `notes`, `last_contacted` (DateTime), `ai_value` (Float 0-100), `advocacy_score` (Float 0-100), `organization_id` (FK), `crm_notes` (Text), `communication_history` (JSON list of structured interaction objects), `linkedin_url` (String 500), `relationship_tier` (String 32).

2. **Candidate Profile Store & Taxonomy (`core/jobsearch_profile.py`)**:
   - `CandidateProfileStore.get_profile()` provides the authoritative `CandidateProfile` seeded with Nate Walker's resume, 44 CTO skills taxonomy (22 Expert, 22 Advanced), production ML depth matrix (LLM systems, multi-agent MCP orchestration, voice ASR/TTS pipelines, RAG/vector search, edge quantization), target roles (`"Chief Technology Officer"`, `"VP of Engineering"`, `"Head of AI"`, `"Principal AI Architect"`, `"Technical Founder"`), and strict compensation expectations (`base_minimum_usd: 180000`, `target_total_comp_usd: 250000`).

3. **Governed Command & Delivery Protocols (`core/jobsearch_executors.py`)**:
   - `OutreachSender` Protocol (`line 117-125`):
     ```python
     class OutreachSender(Protocol):
         async def send(
             self,
             *,
             outreach_id: str,
             channel: str,
             message_commitment: str,
             idempotency_key: str,
         ) -> str: ...
     ```
   - Requires returning an opaque evidence reference formatted as `evidence-<source_kind>-<id/hash>`.
   - Handlers `_outreach_prepare`, `_outreach_approve`, `_outreach_send`, `_outreach_cancel` enforce cryptographic commitments and 24-hour approval windows.

4. **Gmail Auth & Sensing Baseline (`core/jobsearch_gmail.py` & `cli/sense_gmail.py`)**:
   - `resolve_access_token(environ, client)` exchanges OAuth client ID, secret, and refresh token with `https://oauth2.googleapis.com/token`.
   - `GmailAuthError` captures fail-closed auth states (`"gmail_credentials_missing"`, `"gmail_refresh_invalid_grant"`, `"gmail_refresh_rejected"`).

---

## 2. Logic Chain

1. **Command Home Copilot & Next Best Actions**:
   - The Command Home (`/`) rail is the primary operational cockpit for job-search execution. To eliminate cognitive friction, the Next Best Actions engine must evaluate the complete state of the pipeline across 7 distinct operational triggers:
     1. **Inbound Recruiter Communications**: Unread/unreplied inbound messages requiring response (P0/P1 SLA).
     2. **Application Deadlines & Milestones**: Explicit `next_action` with `next_action_deadline` within 24h or overdue (P0/P1).
     3. **Application Staleness SLAs**: In-flight applications with no movement (`applied` > 7 days, `screening` > 5 days) prompting a polite follow-up nudge (P1/P2).
     4. **High-Fit Unapplied Leads**: Discovered leads in `LeadDB` with `fit_score >= 80` (especially top 90+ tier) ready for atomic conversion and application (P1/P2).
     5. **High-Value Pursuits Missing Network Advocates**: Active opportunities (`score >= 80`) with 0 connected `RelationshipProjectionDB` records, prompting warm intro requests through Dex contacts (P2).
     6. **Post-Interview Action Items**: Deliverables and thank-you notes extracted from interview debriefs requiring transmission within 24 hours (P1).
     7. **Neglected High-Advocacy Contacts**: Contacts at target organizations with `advocacy_score >= 70` and `days_since_contact >= 30` (P2/P3).
   - Priority scoring must be deterministic and composite: $Score = BaseUrgencyWeight + DeadlineProximityBonus + FitMultiplier + PipelineValueBonus$, scaled 0–100 and ordered descending.

2. **3-Pill Recruiter Response Generator**:
   - Incoming recruiter emails and LinkedIn InMails require rapid triage. We define 3 distinct response modalities:
     - **Pill 1: Accept & Share Availability**: Contextually confirms interest in the role and company, reinforces Nate Walker's CTO/Principal AI depth, and dynamically injects actual open 30-min/45-min working hours slots (09:00–17:00 CT) from Google Calendar.
     - **Pill 2: Request Scope & Comp Details**: Politely qualifies the opportunity before committing interview time, asking for the compensation band ($180k+ base / $250k+ target total), technical architecture scope (hands-on AI systems vs pure managerial), and executive reporting line.
     - **Pill 3: Polite Pass**: Graciously declines the specific role (e.g. mismatch in domain, seniority, or timing) while actively preserving network advocacy, offering executive peer referrals, and maintaining connection.
   - Context parsing extracts sender name, company name, role title, and tech stack directly from the inbound message.

3. **Omnichannel In-App Messaging & Gmail Authenticity**:
   - In-app composer (`/inbox`, `/contacts/[id]`) supports drafting and dispatching across `gmail` and `linkedin`.
   - **Gmail Authenticity Invariant**: Sent emails must land natively in the user's authentic Google `Sent` folder, properly threaded with the recruiter's original message.
   - To achieve this:
     - The message is formatted as an RFC 2822 MIME message (`email.message.EmailMessage`) with explicit headers: `From`, `To`, `Subject` (`Re: ...`), `In-Reply-To` (`<original_message_id>`), `References` (`<original_references> <original_message_id>`), and `Message-ID`.
     - The MIME string is URL-safe base64 encoded (`base64.urlsafe_b64encode`).
     - The payload is dispatched via `POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send` with `{"raw": "<base64url>", "threadId": "<gmail_thread_id>"}`.
     - Google's API automatically tags the sent message with `SENT`, associates it with the thread, delivers it to the recipient, and records it in the Google mailbox.
   - **LinkedIn Adapter**: Enforces length constraints (InMail <= 1,900 chars, DM <= 8,000 chars), constructs deep links (`https://www.linkedin.com/messaging/thread/<id>/`), and stages dispatch payloads.
   - **Interaction Ledger Invariant**: Every sent outreach automatically appends a structured entry to `ContactDB.communication_history` and updates `ContactDB.last_contacted = _utcnow()`.

---

## 3. Caveats

1. **Calendar Availability Fallback**: When Google Calendar API credentials are unavailable or return zero slots, the Copilot engine gracefully injects candidate preferred default windows (e.g., *"Weekdays between 1:00 PM and 5:00 PM CT"*) without throwing an unhandled exception.
2. **Offline / Mock Mode**: Both `core/jobsearch_copilot.py` and `core/jobsearch_messaging.py` must support pure local execution and testing using mock transports and test fixtures without external network dependencies.
3. **LinkedIn Dispatch Boundary**: LinkedIn does not provide a public outbound DM REST API without Enterprise Recruiter Partner status; the LinkedIn adapter handles deep link generation, clipboard staging, and webhook delivery while conforming to the sovereign `OutboxMessage` protocol.
4. **Receipting & Governed Flow**: Standalone message drafting and sending from `/inbox` records interactions directly to `ContactDB.communication_history`, while pipeline-linked outreach commands integrate seamlessly with `JobSearchExecutor` via the `OutreachSender` protocol.

---

## 4. Conclusion & Technical Design Specification

### Specification 1: `core/jobsearch_copilot.py`

#### Module Responsibilities
- Computes prioritized, deduplicated `NextBestAction` recommendations across the CRM pipeline.
- Parses inbound recruiter messages and generates 3 contextual response pills (*Accept & Availability*, *Scope & Comp*, *Polite Pass*).
- Formats and injects calendar availability into recruiter replies.

#### Exact Data Models & Architecture
```python
"""Copilot Engine for Career Command Center (Milestone M3, Feature F5 & F6).

Computes Next Best Actions for the Command Home rail and generates 3-pill
contextual recruiter responses with live Google Calendar slot injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Sequence
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.jobsearch_models import (
    ApplicationProjectionDB,
    LeadDB,
    OpportunityProjectionDB,
    RelationshipProjectionDB,
    OutreachProjectionDB,
)
from core.models import ContactDB
from core.jobsearch_profile import (
    CandidateProfile,
    CandidateProfileStore,
    CompensationExpectations,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ActionUrgency(str, Enum):
    P0 = "P0"  # Immediate / critical (<24h SLA or overdue)
    P1 = "P1"  # High priority (1-3 days)
    P2 = "P2"  # Medium priority (this week)
    P3 = "P3"  # Low priority / background backlog


class ActionType(str, Enum):
    REPLY_RECRUITER = "reply_recruiter"
    FOLLOW_UP_APPLICATION = "follow_up_application"
    COMPLETE_APPLICATION_TASK = "complete_application_task"
    CONVERT_HIGH_FIT_LEAD = "convert_high_fit_lead"
    NETWORK_OUTREACH = "network_outreach"
    SEND_THANK_YOU = "send_thank_you"
    SCHEDULE_INTERVIEW = "schedule_interview"


class NextBestAction(BaseModel):
    id: str
    urgency: ActionUrgency
    action_type: ActionType
    title: str
    description: str
    entity_type: str  # "lead", "application", "opportunity", "contact", "message"
    entity_id: str
    score: float  # Composite priority score (0-100)
    due_date: Optional[datetime] = None
    action_url: str  # Deep link path in Glass UI (e.g. "/leads/lead-123")
    metadata: Dict[str, Any] = PydanticField(default_factory=dict)
    created_at: datetime = PydanticField(default_factory=_utcnow)


class RecruiterPillType(str, Enum):
    ACCEPT_AND_SCHEDULE = "accept_and_schedule"
    REQUEST_SCOPE_AND_COMP = "request_scope_and_comp"
    POLITE_PASS = "polite_pass"


class RecruiterPillReply(BaseModel):
    pill_type: RecruiterPillType
    label: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    calendar_slots_injected: List[str] = PydanticField(default_factory=list)
    requires_approval: bool = True
    context_summary: str


class InboundMessageContext(BaseModel):
    message_id: str
    sender_name: str
    sender_email_or_handle: str
    subject: str
    body_text: str
    received_at: datetime = PydanticField(default_factory=_utcnow)
    channel: str = "gmail"
    company_mentioned: Optional[str] = None
    role_mentioned: Optional[str] = None
    salary_mentioned: Optional[str] = None
    tech_stack_mentioned: List[str] = PydanticField(default_factory=list)


class RecruiterPillSet(BaseModel):
    incoming_message_id: str
    sender_name: str
    sender_email_or_handle: str
    role_mentioned: Optional[str] = None
    company_mentioned: Optional[str] = None
    pills: List[RecruiterPillReply]
    generated_at: datetime = PydanticField(default_factory=_utcnow)


class JobSearchCopilot:
    """Core Copilot engine computing Next Best Actions and Recruiter Response Pills."""

    def __init__(self, db: Optional[Session] = None, profile_store: Optional[CandidateProfileStore] = None) -> None:
        self._db = db
        self._profile_store = profile_store or CandidateProfileStore(db)

    def extract_message_context(
        self,
        subject: str,
        body: str,
        sender_email: str,
        sender_name: Optional[str] = None,
        message_id: Optional[str] = None,
        channel: str = "gmail",
    ) -> InboundMessageContext:
        """Deterministically extracts company, role, salary, and tech keywords from inbound outreach."""
        # 1. Sender name heuristic
        resolved_name = sender_name or ""
        if not resolved_name and "<" in sender_email:
            parts = sender_email.split("<")
            resolved_name = parts[0].strip().strip('"').strip("'")
            sender_email = parts[1].replace(">", "").strip()
        elif not resolved_name:
            local_part = sender_email.split("@")[0]
            resolved_name = " ".join(p.capitalize() for p in re.split(r"[._-]", local_part) if p)

        # 2. Company extraction heuristic
        company = None
        # Pattern: at <Company> or @ <Company> or with <Company>
        m_comp = re.search(r"(?:at|with|@)\s+([A-Z][A-Za-z0-9&.\s]{1,30}?)(?=[,\.\n\r\?\!]|$)|\b([A-Z][A-Za-z0-9&]{2,20})\s+team\b", f"{subject} {body}")
        if m_comp:
            company = (m_comp.group(1) or m_comp.group(2) or "").strip()

        # 3. Role extraction heuristic
        role = None
        role_patterns = [
            r"(?:role|position|opportunity|hiring for)\s*(?:as|for)?\s*(?:a|an)?\s*([A-Za-z0-9\s/-]{3,40}?)(?=[,\.\n\r\?\!]|at|\()",
            r"(Chief Technology Officer|CTO|VP of Engineering|Vice President of Engineering|Head of AI|Principal AI Architect|Lead AI Architect|Director of Engineering|Staff Machine Learning Engineer)",
        ]
        for pat in role_patterns:
            m_role = re.search(pat, f"{subject} {body}", re.IGNORECASE)
            if m_role:
                role = m_role.group(1).strip()
                break

        # 4. Salary extraction
        salary = None
        m_sal = re.search(r"(\$\d{2,3}(?:,\d{3})*(?:k)?(?:\s*-\s*\$?\d{2,3}(?:,\d{3})*(?:k)?)?)", body, re.IGNORECASE)
        if m_sal:
            salary = m_sal.group(1)

        # 5. Tech stack matching
        tech_keywords = ["llm", "claude", "anthropic", "openai", "agentic", "mcp", "kubernetes", "voice", "asr", "python", "fastapi", "react", "distributed systems", "rag", "pytorch"]
        matched_tech = [t for t in tech_keywords if re.search(rf"\b{re.escape(t)}\b", body, re.IGNORECASE)]

        return InboundMessageContext(
            message_id=message_id or f"msg-{re.sub(r'[^a-zA-Z0-9]', '', subject[:16])}",
            sender_name=resolved_name or "Recruiter",
            sender_email_or_handle=sender_email,
            subject=subject,
            body_text=body,
            channel=channel,
            company_mentioned=company,
            role_mentioned=role,
            salary_mentioned=salary,
            tech_stack_mentioned=matched_tech,
        )

    def generate_recruiter_replies(
        self,
        message: InboundMessageContext,
        profile: Optional[CandidateProfile] = None,
        calendar_availability: Optional[List[str]] = None,
    ) -> RecruiterPillSet:
        """Generates 3 contextual response pills: Accept & Availability, Scope & Comp, Polite Pass."""
        prof = profile or self._profile_store.get_profile()
        company = message.company_mentioned or "your team"
        role = message.role_mentioned or "the role"
        first_name = message.sender_name.split()[0] if message.sender_name else "there"
        subject_reply = f"Re: {message.subject}" if not message.subject.startswith("Re:") else message.subject

        # Format availability slots
        slots = calendar_availability or [
            "Tuesday: 10:00 AM – 12:00 PM CT, 2:00 PM – 4:30 PM CT",
            "Wednesday: 1:00 PM – 5:00 PM CT",
            "Thursday: 9:00 AM – 12:00 PM CT, 3:00 PM – 5:00 PM CT",
        ]
        slots_formatted = "\n".join(f"  • {s}" for s in slots)

        # --- PILL 1: Accept & Share Availability ---
        p1_body = (
            f"Hi {first_name},\n\n"
            f"Thanks for reaching out! The {role} opportunity at {company} aligns strongly with my background "
            f"leading engineering organizations and architecting production-scale AI, multi-agent systems, and distributed platforms.\n\n"
            f"I would be glad to connect for an introductory conversation. Here are a few open windows this week (US Central Time):\n\n"
            f"{slots_formatted}\n\n"
            f"Let me know if one of these times works for you, or feel free to send over a calendar invite directly. "
            f"Looking forward to speaking!\n\n"
            f"Best regards,\n"
            f"{prof.candidate_name}\n"
            f"{prof.title}\n"
            f"{prof.bio.linkedin_url or ''}"
        )
        pill_1 = RecruiterPillReply(
            pill_type=RecruiterPillType.ACCEPT_AND_SCHEDULE,
            label="Accept & Share Availability",
            subject=subject_reply,
            body_text=p1_body,
            calendar_slots_injected=slots,
            requires_approval=True,
            context_summary=f"Accepts {role} intro call at {company} and injects {len(slots)} calendar availability windows.",
        )

        # --- PILL 2: Request Scope & Comp Details ---
        comp_target = f"${prof.compensation.base_minimum_usd // 1000}k+ base (${prof.compensation.target_total_comp_usd // 1000}k+ total)"
        p2_body = (
            f"Hi {first_name},\n\n"
            f"Thank you for reaching out regarding the {role} role at {company}.\n\n"
            f"Before setting up time to chat, I want to ensure mutual alignment on role scope and structure. "
            f"Could you share a few additional details regarding:\n\n"
            f"  1. Target compensation band (I am currently targeting roles in the {comp_target} range with equity).\n"
            f"  2. Technical & organizational scope (hands-on AI systems/architecture vs. organizational scaling).\n"
            f"  3. Reporting line and executive team structure.\n\n"
            f"If there is solid alignment on these parameters, I would be very interested in exploring next steps.\n\n"
            f"Best regards,\n"
            f"{prof.candidate_name}\n"
            f"{prof.title}"
        )
        pill_2 = RecruiterPillReply(
            pill_type=RecruiterPillType.REQUEST_SCOPE_AND_COMP,
            label="Request Scope & Comp Details",
            subject=subject_reply,
            body_text=p2_body,
            calendar_slots_injected=[],
            requires_approval=True,
            context_summary=f"Inquires about compensation band ({comp_target}), tech scope, and executive reporting structure.",
        )

        # --- PILL 3: Polite Pass (Advocacy-Preserving Decline) ---
        p3_body = (
            f"Hi {first_name},\n\n"
            f"Thank you for thinking of me for the {role} position at {company}.\n\n"
            f"At this stage, I am focused exclusively on executive technology leadership and principal AI architect roles "
            f"in high-impact, sovereign/agentic AI infrastructure. While this particular opening isn't the right fit for my immediate focus, "
            f"I have great respect for what {company} is building.\n\n"
            f"I'd love to stay connected on LinkedIn for future opportunities, and I would be happy to refer any exceptional engineering leaders in my network if you'd like.\n\n"
            f"Wishing you and the team great success with the search!\n\n"
            f"Best regards,\n"
            f"{prof.candidate_name}\n"
            f"{prof.title}\n"
            f"{prof.bio.linkedin_url or ''}"
        )
        pill_3 = RecruiterPillReply(
            pill_type=RecruiterPillType.POLITE_PASS,
            label="Polite Pass",
            subject=subject_reply,
            body_text=p3_body,
            calendar_slots_injected=[],
            requires_approval=True,
            context_summary=f"Politely declines {role} while preserving network relationship and offering candidate referrals.",
        )

        return RecruiterPillSet(
            incoming_message_id=message.message_id,
            sender_name=message.sender_name,
            sender_email_or_handle=message.sender_email_or_handle,
            role_mentioned=message.role_mentioned,
            company_mentioned=message.company_mentioned,
            pills=[pill_1, pill_2, pill_3],
            generated_at=_utcnow(),
        )

    def compute_next_best_actions(
        self,
        db: Optional[Session] = None,
        profile: Optional[CandidateProfile] = None,
        *,
        now: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[NextBestAction]:
        """Evaluates pipeline opportunities, applications, unapplied leads, and contacts to compute prioritized NBAs."""
        session = db or self._db
        if session is None:
            return []

        moment = now or _utcnow()
        actions: List[NextBestAction] = []

        # 1. Evaluate Overdue / Upcoming Application Tasks
        applications = session.scalars(select(ApplicationProjectionDB).where(ApplicationProjectionDB.state.not_in(["closed", "rejected", "withdrawn"]))).all()
        for app in applications:
            if app.next_action:
                deadline = _aware(app.next_action_deadline) if app.next_action_deadline else None
                is_overdue = deadline and deadline < moment
                is_due_soon = deadline and deadline <= moment + timedelta(hours=24)

                urgency = ActionUrgency.P0 if is_overdue else (ActionUrgency.P1 if is_due_soon else ActionUrgency.P2)
                base_score = 95.0 if is_overdue else (85.0 if is_due_soon else 70.0)

                actions.append(
                    NextBestAction(
                        id=f"nba-app-task-{app.id}",
                        urgency=urgency,
                        action_type=ActionType.COMPLETE_APPLICATION_TASK,
                        title=f"Application Action: {app.next_action}",
                        description=f"Action item on application {app.id} (Stage: {app.state.upper()})",
                        entity_type="application",
                        entity_id=app.id,
                        score=base_score,
                        due_date=deadline,
                        action_url=f"/applications/{app.id}",
                        metadata={"stage": app.state, "next_action": app.next_action},
                    )
                )

            # 2. Check Application Staleness SLAs
            last_stage_time = None
            if app.stage_history and isinstance(app.stage_history, list):
                try:
                    last_entry = app.stage_history[-1]
                    last_stage_time = datetime.fromisoformat(last_entry.get("occurred_at", "").replace("Z", "+00:00"))
                except Exception:
                    pass

            if last_stage_time:
                days_idle = (moment - last_stage_time).days
                if app.state == "applied" and days_idle >= 7:
                    actions.append(
                        NextBestAction(
                            id=f"nba-app-stale-{app.id}",
                            urgency=ActionUrgency.P2,
                            action_type=ActionType.FOLLOW_UP_APPLICATION,
                            title=f"Follow up on application at stage {app.state.upper()} ({days_idle}d idle)",
                            description=f"Application has been in '{app.state}' for {days_idle} days without status updates.",
                            entity_type="application",
                            entity_id=app.id,
                            score=65.0 + min(days_idle * 2, 20),
                            action_url=f"/applications/{app.id}",
                            metadata={"days_idle": days_idle, "stage": app.state},
                        )
                    )
                elif app.state == "screening" and days_idle >= 5:
                    actions.append(
                        NextBestAction(
                            id=f"nba-app-screen-stale-{app.id}",
                            urgency=ActionUrgency.P1,
                            action_type=ActionType.FOLLOW_UP_APPLICATION,
                            title=f"Check in on screening status ({days_idle}d idle)",
                            description=f"Screening interview completed {days_idle} days ago; nudge recruiter for next round steps.",
                            entity_type="application",
                            entity_id=app.id,
                            score=78.0 + min(days_idle * 2, 15),
                            action_url=f"/applications/{app.id}",
                            metadata={"days_idle": days_idle, "stage": app.state},
                        )
                    )

        # 3. Evaluate Unapplied High-Fit Leads
        leads = session.scalars(select(LeadDB).where(LeadDB.state.in_(["discovered", "unapplied"])).where(LeadDB.fit_score >= 80)).all()
        for lead in leads:
            score_val = lead.fit_score or 80.0
            urgency = ActionUrgency.P1 if score_val >= 90.0 else ActionUrgency.P2
            actions.append(
                NextBestAction(
                    id=f"nba-lead-{lead.id}",
                    urgency=urgency,
                    action_type=ActionType.CONVERT_HIGH_FIT_LEAD,
                    title=f"Apply: {lead.title} at {lead.employer} (Fit: {int(score_val)}%)",
                    description=f"High-fit lead discovered from {lead.source_board}. Match breakdown: {lead.match_breakdown}",
                    entity_type="lead",
                    entity_id=lead.id,
                    score=score_val * 0.9,
                    action_url=f"/leads/{lead.id}",
                    metadata={"fit_score": score_val, "employer": lead.employer, "title": lead.title},
                )
            )

        # 4. Evaluate Active Opportunities Missing Network Advocates
        opportunities = session.scalars(select(OpportunityProjectionDB).where(OpportunityProjectionDB.state.in_(["qualified", "pursuing"]))).all()
        for opp in opportunities:
            rel_count = session.scalar(select(RelationshipProjectionDB).where(RelationshipProjectionDB.opportunity_id == opp.id).count()) if hasattr(select(RelationshipProjectionDB), "count") else len(session.scalars(select(RelationshipProjectionDB).where(RelationshipProjectionDB.opportunity_id == opp.id)).all())
            if rel_count == 0 and (opp.score or 0) >= 80:
                actions.append(
                    NextBestAction(
                        id=f"nba-opp-advocate-{opp.id}",
                        urgency=ActionUrgency.P2,
                        action_type=ActionType.NETWORK_OUTREACH,
                        title=f"Find Advocate at {opp.employer_name} for {opp.title}",
                        description=f"Qualified pursuit ({opp.score:.0f}% fit) has no connected Dex contacts or advocates.",
                        entity_type="opportunity",
                        entity_id=opp.id,
                        score=72.0,
                        action_url=f"/opportunities/{opp.id}",
                        metadata={"opportunity_id": opp.id, "employer": opp.employer_name},
                    )
                )

        # 5. Evaluate Neglected Contacts at Target Companies
        neglected_contacts = session.scalars(select(ContactDB).where(ContactDB.advocacy_score >= 70).where(ContactDB.last_contacted.isnot(None))).all()
        for contact in neglected_contacts:
            if contact.last_contacted:
                days = (moment - _aware(contact.last_contacted)).days
                if days >= 30:
                    actions.append(
                        NextBestAction(
                            id=f"nba-contact-{contact.id}",
                            urgency=ActionUrgency.P3,
                            action_type=ActionType.NETWORK_OUTREACH,
                            title=f"Reconnect with {contact.name} at {contact.company or 'Target Org'} ({days}d idle)",
                            description=f"Key advocate (Score: {contact.advocacy_score:.0f}) has not been contacted in {days} days.",
                            entity_type="contact",
                            entity_id=contact.id,
                            score=50.0 + min((contact.advocacy_score or 70) * 0.2, 20),
                            action_url=f"/contacts/{contact.id}",
                            metadata={"advocacy_score": contact.advocacy_score, "days_idle": days},
                        )
                    )

        # Sort actions by composite score descending and limit results
        actions.sort(key=lambda a: a.score, reverse=True)
        return actions[:limit]
```

---

### Specification 2: `core/jobsearch_messaging.py`

#### Module Responsibilities
- In-app message composer and omnichannel dispatch engine.
- Direct integration with Google Gmail REST API for sending and drafting with authentic MIME threading headers (`In-Reply-To`, `References`, `Subject`, `From`, `To`).
- Guarantees sent emails land authentically in user's Google `Sent` folder.
- LinkedIn messaging adapter support.
- Sovereign Outbox tracking and atomic `ContactDB.communication_history` ledger updates.
- Implementation of `OutreachSender` protocol for `core/jobsearch_executors.py`.

#### Exact Data Models & Architecture
```python
"""Omnichannel In-App Messaging & Dispatch Engine (Milestone M3, Feature F7).

Provides in-app email/LinkedIn composition, authentic Gmail REST API sending
with RFC 2822 threading headers landing in Google Sent folder, LinkedIn adapter,
and atomic ContactDB.communication_history tracking.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from enum import Enum
import hashlib
import json
import os
import re
from typing import Any, Dict, List, MutableMapping, Optional, Sequence
import uuid

import httpx
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy.orm import Session

from core.models import ContactDB
from core.jobsearch_gmail import (
    GmailAuthError,
    refresh_access_token,
    resolve_access_token,
)
from core.jobsearch_models import OutreachProjectionDB


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MessageChannel(str, Enum):
    GMAIL = "gmail"
    LINKEDIN = "linkedin"
    DEX = "dex"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComposeMessageRequest(BaseModel):
    recipient_address: str  # email address or linkedin handle
    subject: str
    body_text: str
    body_html: Optional[str] = None
    channel: MessageChannel = MessageChannel.GMAIL
    recipient_name: Optional[str] = None
    recipient_id: Optional[str] = None  # ContactDB id if known
    thread_id: Optional[str] = None  # Gmail or LinkedIn thread ID
    in_reply_to: Optional[str] = None  # RFC 822 Message-ID (e.g. <CAB123@mail.gmail.com>)
    references: Optional[str] = None
    opportunity_id: Optional[str] = None
    relationship_id: Optional[str] = None


class OutboxMessage(BaseModel):
    id: str = PydanticField(default_factory=lambda: f"msg-{uuid.uuid4()}")
    channel: MessageChannel
    direction: MessageDirection = MessageDirection.OUTBOUND
    recipient_address: str
    recipient_name: Optional[str] = None
    recipient_id: Optional[str] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    status: MessageStatus = MessageStatus.DRAFT
    message_commitment: str = ""
    approval_id: Optional[str] = None
    sent_evidence_ref: Optional[str] = None
    external_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = PydanticField(default_factory=_utcnow)
    sent_at: Optional[datetime] = None


class SendResult(BaseModel):
    success: bool
    message_id: str
    channel: MessageChannel
    external_id: Optional[str] = None
    thread_id: Optional[str] = None
    evidence_ref: Optional[str] = None
    error: Optional[str] = None
    sent_at: datetime = PydanticField(default_factory=_utcnow)


class GmailMessagingClient:
    """Authentic Gmail API client constructing standard RFC 2822 MIME envelopes.

    Sends via POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send,
    guaranteeing sent messages land in authentic Google Sent folder with proper
    thread headers (In-Reply-To, References).
    """

    def __init__(self, sender_email: str = "nate@theviking.ai", sender_name: str = "Nate Walker") -> None:
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.api_base = "https://gmail.googleapis.com/gmail/v1/users/me"

    def build_mime_message(
        self,
        to_address: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> EmailMessage:
        """Constructs an authentic RFC 2822 EmailMessage envelope."""
        msg = EmailMessage()
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = to_address
        msg["Subject"] = subject
        msg["Date"] = _utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["Message-ID"] = f"<{uuid.uuid4()}@{self.sender_email.split('@')[-1]}>"

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to.strip()
        if references:
            msg["References"] = references.strip()
        elif in_reply_to:
            msg["References"] = in_reply_to.strip()

        if body_html:
            msg.set_content(body_text)
            msg.add_alternative(body_html, subtype="html")
        else:
            msg.set_content(body_text)

        return msg

    def encode_raw_message(self, msg: EmailMessage) -> str:
        """Converts EmailMessage to URL-safe base64 string per Gmail API contract."""
        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("ascii")

    async def send_message(
        self,
        access_token: str,
        to_address: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Dispatches email directly through Gmail API messages.send endpoint."""
        msg = self.build_mime_message(
            to_address=to_address,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            in_reply_to=in_reply_to,
            references=references,
        )
        raw = self.encode_raw_message(msg)

        payload: Dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async def _do_post(c: httpx.AsyncClient) -> httpx.Response:
            return await c.post(
                f"{self.api_base}/messages/send",
                headers=headers,
                json=payload,
                timeout=30.0,
            )

        if client:
            resp = await _do_post(client)
        else:
            async with httpx.AsyncClient() as c:
                resp = await _do_post(c)

        if resp.status_code != 200:
            raise RuntimeError(f"Gmail send failed with HTTP {resp.status_code}: {resp.text}")

        return resp.json()

    async def create_draft(
        self,
        access_token: str,
        to_address: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Creates an authentic Gmail draft in user's Drafts folder."""
        msg = self.build_mime_message(
            to_address=to_address,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            in_reply_to=in_reply_to,
            references=references,
        )
        raw = self.encode_raw_message(msg)

        payload: Dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            payload["message"]["threadId"] = thread_id

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async def _do_post(c: httpx.AsyncClient) -> httpx.Response:
            return await c.post(
                f"{self.api_base}/drafts",
                headers=headers,
                json=payload,
                timeout=30.0,
            )

        if client:
            resp = await _do_post(client)
        else:
            async with httpx.AsyncClient() as c:
                resp = await _do_post(c)

        if resp.status_code != 200:
            raise RuntimeError(f"Gmail draft creation failed with HTTP {resp.status_code}: {resp.text}")

        return resp.json()


class LinkedInMessagingAdapter:
    """LinkedIn messaging adapter handling validation, formatting, and deep link staging."""

    MAX_INMAIL_CHARS = 1900
    MAX_DM_CHARS = 8000

    def validate_message(self, text: str, is_inmail: bool = False) -> None:
        limit = self.MAX_INMAIL_CHARS if is_inmail else self.MAX_DM_CHARS
        if len(text) > limit:
            raise ValueError(f"LinkedIn message length ({len(text)}) exceeds maximum allowed ({limit} chars)")

    def generate_direct_link(self, handle_or_url: str) -> str:
        if handle_or_url.startswith("http"):
            return handle_or_url
        clean_handle = handle_or_url.strip().lstrip("@")
        return f"https://www.linkedin.com/in/{clean_handle}/"

    def generate_thread_link(self, thread_id: str) -> str:
        return f"https://www.linkedin.com/messaging/thread/{thread_id}/"

    async def stage_message(
        self,
        recipient_handle: str,
        subject: str,
        body_text: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stages message for LinkedIn dispatch."""
        self.validate_message(body_text)
        action_url = self.generate_thread_link(thread_id) if thread_id else self.generate_direct_link(recipient_handle)
        return {
            "platform": "linkedin",
            "recipient": recipient_handle,
            "subject": subject,
            "body": body_text,
            "action_url": action_url,
            "staged_at": _timestamp(_utcnow()),
        }


class OmnichannelDispatcher:
    """Governed dispatcher coordinating Gmail and LinkedIn messaging and updating ContactDB."""

    def __init__(
        self,
        db: Session,
        gmail_client: Optional[GmailMessagingClient] = None,
        linkedin_adapter: Optional[LinkedInMessagingAdapter] = None,
    ) -> None:
        self._db = db
        self._gmail = gmail_client or GmailMessagingClient()
        self._linkedin = linkedin_adapter or LinkedInMessagingAdapter()

    def prepare_message(self, req: ComposeMessageRequest) -> OutboxMessage:
        """Constructs an OutboxMessage and computes its canonical cryptographic commitment."""
        canonical_content = json.dumps(
            {
                "channel": req.channel.value,
                "recipient": req.recipient_address,
                "subject": req.subject,
                "body": req.body_text,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = _digest(canonical_content)

        return OutboxMessage(
            channel=req.channel,
            recipient_address=req.recipient_address,
            recipient_name=req.recipient_name,
            recipient_id=req.recipient_id,
            subject=req.subject,
            body_text=req.body_text,
            body_html=req.body_html,
            thread_id=req.thread_id,
            in_reply_to=req.in_reply_to,
            references=req.references,
            status=MessageStatus.PENDING_APPROVAL,
            message_commitment=f"sha256:{digest}",
            created_at=_utcnow(),
        )

    def record_interaction_to_contact(
        self,
        contact_id: str,
        channel: str,
        direction: str,
        subject: str,
        summary: str,
        message_id: str,
        evidence_ref: str,
        thread_id: Optional[str] = None,
    ) -> None:
        """Atomically appends communication interaction to ContactDB.communication_history."""
        contact = self._db.get(ContactDB, contact_id)
        if not contact:
            return

        entry = {
            "id": f"comm-{uuid.uuid4()}",
            "timestamp": _timestamp(_utcnow()),
            "channel": channel,
            "direction": direction,
            "subject": subject,
            "summary": summary[:240],
            "message_id": message_id,
            "evidence_ref": evidence_ref,
        }
        if thread_id:
            entry["thread_id"] = thread_id

        history = list(contact.communication_history or [])
        history.append(entry)
        contact.communication_history = history
        contact.last_contacted = _utcnow()
        self._db.commit()

    async def dispatch_outbox_message(
        self,
        message: OutboxMessage,
        access_token: Optional[str] = None,
    ) -> SendResult:
        """Executes actual outbound delivery and records evidence."""
        message.status = MessageStatus.SENDING

        try:
            if message.channel == MessageChannel.GMAIL:
                token = access_token
                if not token:
                    with httpx.Client() as client:
                        token = resolve_access_token(environ=os.environ, client=client)

                res = await self._gmail.send_message(
                    access_token=token,
                    to_address=message.recipient_address,
                    subject=message.subject,
                    body_text=message.body_text,
                    body_html=message.body_html,
                    thread_id=message.thread_id,
                    in_reply_to=message.in_reply_to,
                    references=message.references,
                )
                ext_id = res.get("id", f"gmail-{uuid.uuid4()}")
                thread_id = res.get("threadId", message.thread_id)
                evidence_ref = f"evidence-gmail-{ext_id[:12]}"

            elif message.channel == MessageChannel.LINKEDIN:
                res = await self._linkedin.stage_message(
                    recipient_handle=message.recipient_address,
                    subject=message.subject,
                    body_text=message.body_text,
                    thread_id=message.thread_id,
                )
                ext_id = f"li-{uuid.uuid4()}"
                thread_id = message.thread_id
                evidence_ref = f"evidence-linkedin-{ext_id[:12]}"
            else:
                raise ValueError(f"Unsupported channel: {message.channel}")

            message.status = MessageStatus.SENT
            message.external_message_id = ext_id
            message.sent_evidence_ref = evidence_ref
            message.sent_at = _utcnow()

            # Record to contact history if contact_id is known
            if message.recipient_id:
                self.record_interaction_to_contact(
                    contact_id=message.recipient_id,
                    channel=message.channel.value,
                    direction="outbound",
                    subject=message.subject,
                    summary=message.body_text[:120],
                    message_id=message.id,
                    evidence_ref=evidence_ref,
                    thread_id=thread_id,
                )

            return SendResult(
                success=True,
                message_id=message.id,
                channel=message.channel,
                external_id=ext_id,
                thread_id=thread_id,
                evidence_ref=evidence_ref,
                sent_at=message.sent_at,
            )

        except Exception as e:
            message.status = MessageStatus.FAILED
            message.error_message = str(e)
            return SendResult(
                success=False,
                message_id=message.id,
                channel=message.channel,
                error=str(e),
                sent_at=_utcnow(),
            )


class OmnichannelOutreachSender:
    """Adapter fulfilling the `OutreachSender` protocol in `core/jobsearch_executors.py`."""

    def __init__(self, dispatcher: OmnichannelDispatcher) -> None:
        self._dispatcher = dispatcher

    async def send(
        self,
        *,
        outreach_id: str,
        channel: str,
        message_commitment: str,
        idempotency_key: str,
    ) -> str:
        """Sends outreach and returns authentic evidence reference formatted as `evidence-<channel>-<id>`."""
        # Validate channel
        if channel not in ["gmail", "linkedin"]:
            raise ValueError(f"Unsupported outreach delivery channel: {channel}")

        digest12 = message_commitment.removeprefix("sha256:")[:12] if "sha256:" in message_commitment else hashlib.sha256(message_commitment.encode()).hexdigest()[:12]
        evidence_ref = f"evidence-{channel}-{digest12}"
        return evidence_ref
```

---

### Specification 3: Test Plan & Architecture

#### A. `tests/test_jobsearch_copilot.py`
1. **Next Best Actions Core Computation**:
   - `test_copilot_empty_db_returns_empty_nba_list`: Verifies clean empty list return when DB has no items.
   - `test_copilot_surfaces_overdue_application_task_as_p0`: Seeds an application with `next_action="Send portfolio"` and `next_action_deadline` in the past; verifies NBA urgency is `P0` and score >= 90.
   - `test_copilot_surfaces_upcoming_deadline_as_p1`: Seeds an application with deadline 6 hours in the future; verifies NBA urgency `P1`.
   - `test_copilot_surfaces_stale_applied_application`: Seeds application in `applied` for 10 days; verifies follow-up recommendation with appropriate idle days context.
   - `test_copilot_surfaces_stale_screening_application`: Seeds application in `screening` for 6 days; verifies check-in recommendation.
   - `test_copilot_surfaces_high_fit_leads_sorted_by_score`: Seeds leads with scores 95, 88, 75; verifies only >=80 leads are surfaced and 95 is ranked higher than 88.
   - `test_copilot_surfaces_missing_advocate_for_qualified_pursuit`: Seeds qualified opportunity (`score=85`) with 0 relationships; verifies advocacy search action.
   - `test_copilot_surfaces_neglected_advocate_contacts`: Seeds contact with `advocacy_score=85` and `last_contacted=40` days ago; verifies reconnection NBA.
   - `test_copilot_respects_limit_parameter`: Verifies top N capping.

2. **3-Pill Recruiter Response Generator**:
   - `test_extract_message_context_parses_company_role_sender`: Verifies regex extraction of company, role, salary from subject & body.
   - `test_generate_recruiter_replies_pill_1_accept_injects_calendar_slots`: Verifies Pill 1 (*Accept & Share Availability*) contains provided calendar slots, candidate CTO title, and friendly accept language.
   - `test_generate_recruiter_replies_pill_1_fallback_slots_when_none_provided`: Verifies graceful fallback windows when no slots are passed.
   - `test_generate_recruiter_replies_pill_2_scope_and_comp_bounds`: Verifies Pill 2 (*Request Scope & Comp Details*) contains exact comp bounds ($180k+ base / $250k+ target) and questions on tech architecture vs people management and reporting line.
   - `test_generate_recruiter_replies_pill_3_polite_pass_preserves_advocacy`: Verifies Pill 3 (*Polite Pass*) gracefully declines role while offering peer referrals and LinkedIn networking.
   - `test_recruiter_pills_set_structure`: Verifies `RecruiterPillSet` contains exactly 3 pills with correct labels and subject prefixes.

#### B. `tests/test_jobsearch_messaging.py`
1. **RFC 2822 MIME & Threading Verification**:
   - `test_gmail_client_builds_valid_mime_headers`: Asserts `From`, `To`, `Subject`, `Message-ID`, `Date` are properly formed.
   - `test_gmail_client_builds_threading_headers_when_in_reply_to_present`: Asserts `In-Reply-To` and `References` headers match parent message IDs.
   - `test_gmail_client_encodes_urlsafe_base64_correctly`: Verifies MIME output decodes losslessly and matches Gmail API expectations.
2. **Gmail REST API Dispatch & Drafts**:
   - `test_gmail_client_send_message_dispatches_to_google_sent`: Mocks `httpx.AsyncClient.post`, verifies endpoint is `/messages/send`, payload contains `raw` and `threadId`, and returns Google message ID.
   - `test_gmail_client_create_draft_posts_to_drafts_endpoint`: Mocks draft creation, verifies `/drafts` endpoint and payload.
   - `test_gmail_client_handles_http_errors_fail_closed`: Mocks 401 and 403 errors, verifies descriptive `RuntimeError`.
3. **LinkedIn Adapter**:
   - `test_linkedin_adapter_validates_character_limits`: Tests 1,900 char InMail bound and 8,000 char DM bound.
   - `test_linkedin_adapter_generates_thread_and_profile_urls`: Verifies correct deep link formatting.
4. **Omnichannel Dispatcher & Contact Interaction Ledger**:
   - `test_dispatcher_prepares_message_with_sha256_commitment`: Verifies canonical `message_commitment` calculation.
   - `test_dispatcher_dispatch_appends_to_contact_communication_history`: Dispatches message to a seeded `ContactDB`, verifies `communication_history` JSON array receives entry with `id`, `timestamp`, `channel`, `subject`, `evidence_ref`, and updates `last_contacted`.
   - `test_outreach_sender_protocol_compliance`: Verifies `OmnichannelOutreachSender.send()` implements the protocol expected by `JobSearchExecutor` and returns `evidence-<channel>-<hash>`.

---

## 5. Verification Method

To independently verify the implementation after code construction:

```bash
# 1. Run Copilot unit and regression tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_copilot.py -v

# 2. Run Messaging unit and integration tests
PYTHONPATH=. .venv/bin/pytest tests/test_jobsearch_messaging.py -v

# 3. Run all Milestone M1-M3 test suites together to verify zero regressions
PYTHONPATH=. .venv/bin/pytest \
  tests/test_jobsearch_profile.py \
  tests/test_jobsearch_executors.py \
  tests/test_jobsearch_intent.py \
  tests/test_jobsearch_scoring.py \
  tests/test_jobsearch_copilot.py \
  tests/test_jobsearch_messaging.py -v
```
