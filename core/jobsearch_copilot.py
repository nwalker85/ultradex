"""Copilot Engine for Career Command Center (Milestone M3, Features F5 & F6).

Computes Next Best Actions for the Command Home rail and generates 3-pill
contextual recruiter responses with live Google Calendar slot injection.
"""

from __future__ import annotations

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
)
from core.models import ContactDB
from core.jobsearch_profile import (
    CandidateProfile,
    CandidateProfileStore,
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

    def __init__(
        self,
        db: Optional[Session] = None,
        profile_store: Optional[CandidateProfileStore] = None,
    ) -> None:
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
        resolved_name = (sender_name or "").strip()
        cleaned_email = sender_email.strip()
        if not resolved_name and "<" in cleaned_email:
            parts = cleaned_email.split("<")
            resolved_name = parts[0].strip().strip('"').strip("'")
            cleaned_email = parts[1].replace(">", "").strip()
        elif not resolved_name and "@" in cleaned_email:
            local_part = cleaned_email.split("@")[0]
            resolved_name = " ".join(p.capitalize() for p in re.split(r"[._-]", local_part) if p)

        # 2. Company extraction heuristic
        company = None
        # Pattern: at <Company> or @ <Company> or with <Company> or <Company> team
        combined_text = f"{subject}\n{body}"
        m_comp = re.search(
            r"(?:at|with|@)\s+([A-Z][A-Za-z0-9&.\s]{1,30}?)(?=[,\.\n\r\?\!]|\s+team|$)",
            combined_text,
        )
        if m_comp and m_comp.group(1):
            company_candidate = m_comp.group(1).strip()
            # Filter out non-company noise words
            if company_candidate.lower() not in {"the", "a", "an", "this", "our", "my", "your", "us"}:
                company = company_candidate
        if not company:
            m_comp2 = re.search(r"\b([A-Z][A-Za-z0-9&]{2,20})\s+team\b", combined_text)
            if m_comp2 and m_comp2.group(1):
                company = m_comp2.group(1).strip()

        # 3. Role extraction heuristic
        role = None
        role_patterns = [
            r"(Chief Technology Officer|CTO|VP of Engineering|Vice President of Engineering|Head of AI|Principal AI Architect|Lead AI Architect|Director of Engineering|Staff Machine Learning Engineer|Staff ML Engineer|Solutions Architect|Principal Architect)",
            r"(?:role|position|opportunity|hiring for)\s*(?:as|for)?\s*(?:a|an)?\s*([A-Za-z0-9\s/-]{3,40}?)(?=[,\.\n\r\?\!]|at|\()",
        ]
        for pat in role_patterns:
            m_role = re.search(pat, combined_text, re.IGNORECASE)
            if m_role and m_role.group(1):
                role = m_role.group(1).strip()
                break

        # 4. Salary extraction
        salary = None
        m_sal = re.search(
            r"(\$\d{2,3}(?:,\d{3})*(?:k)?(?:\s*-\s*\$?\d{2,3}(?:,\d{3})*(?:k)?)?)",
            combined_text,
            re.IGNORECASE,
        )
        if m_sal:
            salary = m_sal.group(1).strip()

        # 5. Tech stack matching
        tech_keywords = [
            "llm",
            "claude",
            "anthropic",
            "openai",
            "agentic",
            "mcp",
            "kubernetes",
            "voice",
            "asr",
            "tts",
            "python",
            "fastapi",
            "react",
            "distributed systems",
            "rag",
            "pytorch",
        ]
        matched_tech = [
            t for t in tech_keywords if re.search(rf"\b{re.escape(t)}\b", combined_text, re.IGNORECASE)
        ]

        return InboundMessageContext(
            message_id=message_id or f"msg-{re.sub(r'[^a-zA-Z0-9]', '', subject[:16])}",
            sender_name=resolved_name or "Recruiter",
            sender_email_or_handle=cleaned_email,
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
        subject_reply = (
            f"Re: {message.subject}"
            if not message.subject.lower().startswith("re:")
            else message.subject
        )

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
        comp_target = (
            f"${prof.compensation.base_minimum_usd // 1000}k+ base (${prof.compensation.target_total_comp_usd // 1000}k+ total)"
            if hasattr(prof, "compensation") and prof.compensation
            else "$180k+ base ($250k+ total)"
        )
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

        # 1. Evaluate Overdue / Upcoming Application Tasks & Staleness
        applications = session.scalars(
            select(ApplicationProjectionDB).where(
                ApplicationProjectionDB.state.not_in(["closed", "rejected", "withdrawn"])
            )
        ).all()

        for app in applications:
            if app.next_action:
                deadline = _aware(app.next_action_deadline) if app.next_action_deadline else None
                is_overdue = deadline is not None and deadline < moment
                is_due_soon = (
                    deadline is not None and not is_overdue and deadline <= moment + timedelta(hours=24)
                )

                urgency = (
                    ActionUrgency.P0
                    if is_overdue
                    else (ActionUrgency.P1 if is_due_soon else ActionUrgency.P2)
                )
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

            # Check Application Staleness SLAs
            last_stage_time = None
            if app.stage_history and isinstance(app.stage_history, list):
                try:
                    last_entry = app.stage_history[-1]
                    raw_dt = last_entry.get("occurred_at", "")
                    if raw_dt:
                        last_stage_time = _aware(
                            datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
                        )
                except Exception:
                    pass

            if last_stage_time is None and app.created_at:
                last_stage_time = _aware(app.created_at)

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

        # 2. Evaluate Unapplied High-Fit Leads (fit_score >= 80)
        leads = session.scalars(
            select(LeadDB)
            .where(LeadDB.state.in_(["discovered", "unapplied"]))
            .where(LeadDB.fit_score >= 80)
        ).all()

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
                    metadata={
                        "fit_score": score_val,
                        "employer": lead.employer,
                        "title": lead.title,
                    },
                )
            )

        # 3. Evaluate Active Opportunities Missing Network Advocates (score >= 80, 0 relationships)
        opportunities = session.scalars(
            select(OpportunityProjectionDB).where(
                OpportunityProjectionDB.state.in_(["qualified", "pursuing"])
            )
        ).all()

        for opp in opportunities:
            rel_matches = session.scalars(
                select(RelationshipProjectionDB).where(
                    RelationshipProjectionDB.opportunity_id == opp.id
                )
            ).all()
            if len(rel_matches) == 0 and (opp.score or 0) >= 80:
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

        # 4. Evaluate Neglected Key Contacts at Target Companies (advocacy_score >= 70, idle >= 30 days)
        neglected_contacts = session.scalars(
            select(ContactDB)
            .where(ContactDB.advocacy_score >= 70)
            .where(ContactDB.last_contacted.isnot(None))
        ).all()

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


# Standalone convenience helpers matching interface contracts
def compute_next_best_actions(
    db: Session,
    profile: Optional[CandidateProfile] = None,
    *,
    now: Optional[datetime] = None,
    limit: int = 10,
) -> List[NextBestAction]:
    copilot = JobSearchCopilot(db=db)
    return copilot.compute_next_best_actions(db=db, profile=profile, now=now, limit=limit)


def generate_recruiter_replies(
    message: InboundMessageContext,
    calendar_availability: Optional[List[str]] = None,
    profile: Optional[CandidateProfile] = None,
) -> RecruiterPillSet:
    copilot = JobSearchCopilot()
    return copilot.generate_recruiter_replies(
        message=message,
        profile=profile,
        calendar_availability=calendar_availability,
    )


def extract_message_context(
    subject: str,
    body: str,
    sender_email: str,
    sender_name: Optional[str] = None,
    message_id: Optional[str] = None,
    channel: str = "gmail",
) -> InboundMessageContext:
    copilot = JobSearchCopilot()
    return copilot.extract_message_context(
        subject=subject,
        body=body,
        sender_email=sender_email,
        sender_name=sender_name,
        message_id=message_id,
        channel=channel,
    )
