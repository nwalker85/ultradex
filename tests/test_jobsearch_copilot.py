"""Tests for Copilot Engine and Recruiter Response Generator (Milestone M3, Features F5 & F6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.models import Base, ContactDB
from core.jobsearch_models import (
    ApplicationProjectionDB,
    LeadDB,
    OpportunityProjectionDB,
    RelationshipProjectionDB,
)
from core.jobsearch_copilot import (
    ActionType,
    ActionUrgency,
    InboundMessageContext,
    JobSearchCopilot,
    NextBestAction,
    RecruiterPillType,
    compute_next_best_actions,
    extract_message_context,
    generate_recruiter_replies,
)
from core.jobsearch_profile import CandidateProfileStore


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_copilot_empty_db_returns_empty_nba_list(db_session: Session) -> None:
    copilot = JobSearchCopilot(db=db_session)
    actions = copilot.compute_next_best_actions()
    assert actions == []


def test_copilot_surfaces_overdue_application_task_as_p0(db_session: Session) -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    app = ApplicationProjectionDB(
        id="app-1",
        opportunity_id="opp-1",
        state="screening",
        stage_history=[{"status": "screening", "occurred_at": "2026-08-20T10:00:00Z"}],
        artifact_refs=[],
        next_action="Submit architecture design doc",
        next_action_deadline=datetime(2026, 8, 23, 17, 0, tzinfo=timezone.utc),  # Overdue
        source_event_id="evt-1",
        source_event_position="1",
    )
    db_session.add(app)
    db_session.commit()

    copilot = JobSearchCopilot(db=db_session)
    actions = copilot.compute_next_best_actions(now=now)

    assert len(actions) >= 1
    overdue_action = next(a for a in actions if a.entity_id == "app-1" and a.action_type == ActionType.COMPLETE_APPLICATION_TASK)
    assert overdue_action.urgency == ActionUrgency.P0
    assert overdue_action.score >= 90.0
    assert "Submit architecture design doc" in overdue_action.title
    assert overdue_action.action_url == "/applications/app-1"


def test_copilot_surfaces_upcoming_deadline_as_p1(db_session: Session) -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    app = ApplicationProjectionDB(
        id="app-2",
        opportunity_id="opp-2",
        state="interviewing",
        stage_history=[{"status": "interviewing", "occurred_at": "2026-08-22T10:00:00Z"}],
        artifact_refs=[],
        next_action="Send reference contacts",
        next_action_deadline=datetime(2026, 8, 24, 20, 0, tzinfo=timezone.utc),  # Due in 8h (<24h)
        source_event_id="evt-2",
        source_event_position="2",
    )
    db_session.add(app)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session, now=now)
    act = next(a for a in actions if a.entity_id == "app-2")
    assert act.urgency == ActionUrgency.P1
    assert act.score == 85.0


def test_copilot_surfaces_stale_applied_application(db_session: Session) -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    app = ApplicationProjectionDB(
        id="app-stale-1",
        opportunity_id="opp-stale-1",
        state="applied",
        stage_history=[{"status": "applied", "occurred_at": "2026-08-10T12:00:00Z"}],  # 14 days idle
        artifact_refs=[],
        next_action=None,
        next_action_deadline=None,
        source_event_id="evt-3",
        source_event_position="3",
    )
    db_session.add(app)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session, now=now)
    act = next(a for a in actions if a.id == "nba-app-stale-app-stale-1")
    assert act.action_type == ActionType.FOLLOW_UP_APPLICATION
    assert act.urgency == ActionUrgency.P2
    assert "14d idle" in act.title
    assert act.metadata["days_idle"] == 14


def test_copilot_surfaces_stale_screening_application(db_session: Session) -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    app = ApplicationProjectionDB(
        id="app-screen-1",
        opportunity_id="opp-screen-1",
        state="screening",
        stage_history=[{"status": "screening", "occurred_at": "2026-08-18T12:00:00Z"}],  # 6 days idle
        artifact_refs=[],
        next_action=None,
        next_action_deadline=None,
        source_event_id="evt-4",
        source_event_position="4",
    )
    db_session.add(app)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session, now=now)
    act = next(a for a in actions if a.id == "nba-app-screen-stale-app-screen-1")
    assert act.action_type == ActionType.FOLLOW_UP_APPLICATION
    assert act.urgency == ActionUrgency.P1
    assert "6d idle" in act.title


def test_copilot_surfaces_high_fit_leads_sorted_by_score(db_session: Session) -> None:
    leads = [
        LeadDB(
            id="lead-low",
            source_board="greenhouse",
            employer="Acme Low",
            title="Junior Dev",
            fit_score=72.0,  # Below 80 threshold -> should NOT surface
            match_breakdown={},
            risk_flags=[],
            state="discovered",
        ),
        LeadDB(
            id="lead-mid",
            source_board="ashby",
            employer="MidCorp",
            title="VP Eng",
            fit_score=85.0,  # >= 80 -> P2
            match_breakdown={"skills": 85},
            risk_flags=[],
            state="unapplied",
        ),
        LeadDB(
            id="lead-high",
            source_board="anthropic",
            employer="Anthropic",
            title="Principal AI Architect",
            fit_score=94.0,  # >= 90 -> P1
            match_breakdown={"skills": 95},
            risk_flags=[],
            state="discovered",
        ),
    ]
    for l in leads:
        db_session.add(l)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session)
    lead_actions = [a for a in actions if a.entity_type == "lead"]

    assert len(lead_actions) == 2
    assert lead_actions[0].entity_id == "lead-high"
    assert lead_actions[0].urgency == ActionUrgency.P1
    assert lead_actions[1].entity_id == "lead-mid"
    assert lead_actions[1].urgency == ActionUrgency.P2


def test_copilot_surfaces_missing_advocate_for_qualified_pursuit(db_session: Session) -> None:
    opp = OpportunityProjectionDB(
        id="opp-adv-1",
        employer_name="Scale AI",
        title="Head of AI Systems",
        state="qualified",
        score=88.0,
        risk_flags=[],
        evidence_refs=[],
        source_event_id="evt-opp-1",
        source_event_position="1",
    )
    db_session.add(opp)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session)
    adv_act = next(a for a in actions if a.id == "nba-opp-advocate-opp-adv-1")
    assert adv_act.action_type == ActionType.NETWORK_OUTREACH
    assert "Scale AI" in adv_act.title


def test_copilot_surfaces_neglected_advocate_contacts(db_session: Session) -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    contact = ContactDB(
        id="contact-1",
        name="Sarah Connor",
        email="sarah@openai.com",
        company="OpenAI",
        job_title="Director of Engineering",
        advocacy_score=85.0,
        last_contacted=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),  # 45 days ago
    )
    db_session.add(contact)
    db_session.commit()

    actions = compute_next_best_actions(db=db_session, now=now)
    c_act = next(a for a in actions if a.id == "nba-contact-contact-1")
    assert c_act.action_type == ActionType.NETWORK_OUTREACH
    assert c_act.urgency == ActionUrgency.P3
    assert "Sarah Connor" in c_act.title


def test_copilot_respects_limit_parameter(db_session: Session) -> None:
    for i in range(15):
        db_session.add(
            LeadDB(
                id=f"lead-bulk-{i}",
                source_board="linkedin",
                employer=f"Corp {i}",
                title=f"Head of AI {i}",
                fit_score=80.0 + i,
                state="discovered",
            )
        )
    db_session.commit()

    actions = compute_next_best_actions(db=db_session, limit=5)
    assert len(actions) == 5


def test_extract_message_context_parses_company_role_sender() -> None:
    subject = "Exciting Head of AI opportunity at Anthropic"
    body = (
        "Hi Nate, I came across your impressive background leading engineering organizations and distributed AI platforms. "
        "We are hiring for a Head of AI role at Anthropic with compensation around $220k - $280k. "
        "Our team works heavily with Python, Kubernetes, LLM orchestration, and MCP. Would love to chat!"
    )
    sender_email = "alex.recruiter@anthropic.com"
    sender_name = "Alex Rivera"

    ctx = extract_message_context(
        subject=subject,
        body=body,
        sender_email=sender_email,
        sender_name=sender_name,
    )

    assert ctx.sender_name == "Alex Rivera"
    assert ctx.sender_email_or_handle == "alex.recruiter@anthropic.com"
    assert ctx.company_mentioned == "Anthropic"
    assert ctx.role_mentioned is not None and "Head of AI" in ctx.role_mentioned
    assert ctx.salary_mentioned is not None and "$220k - $280k" in ctx.salary_mentioned
    assert "llm" in ctx.tech_stack_mentioned
    assert "kubernetes" in ctx.tech_stack_mentioned
    assert "mcp" in ctx.tech_stack_mentioned


def test_generate_recruiter_replies_pill_1_accept_injects_calendar_slots() -> None:
    ctx = InboundMessageContext(
        message_id="msg-101",
        sender_name="Sarah Chen",
        sender_email_or_handle="sarah@deepgram.com",
        subject="Intro call: VP of Engineering at Deepgram",
        body_text="Hi Nate, would love to connect this week regarding the VP of Engineering role.",
        company_mentioned="Deepgram",
        role_mentioned="VP of Engineering",
    )

    slots = [
        "Tuesday, Aug 25: 10:00 AM – 12:00 PM CT",
        "Wednesday, Aug 26: 01:00 PM – 04:30 PM CT",
    ]

    pill_set = generate_recruiter_replies(message=ctx, calendar_availability=slots)
    assert len(pill_set.pills) == 3

    p1 = next(p for p in pill_set.pills if p.pill_type == RecruiterPillType.ACCEPT_AND_SCHEDULE)
    assert p1.label == "Accept & Share Availability"
    assert "Re: Intro call: VP of Engineering at Deepgram" in p1.subject
    assert "Tuesday, Aug 25: 10:00 AM – 12:00 PM CT" in p1.body_text
    assert "Wednesday, Aug 26: 01:00 PM – 04:30 PM CT" in p1.body_text
    assert "Nate Walker" in p1.body_text
    assert p1.requires_approval is True


def test_generate_recruiter_replies_pill_1_fallback_slots_when_none_provided() -> None:
    ctx = InboundMessageContext(
        message_id="msg-102",
        sender_name="David Miller",
        sender_email_or_handle="david@openai.com",
        subject="Chat about CTO Office",
        body_text="Hi Nate, let's chat.",
        company_mentioned="OpenAI",
        role_mentioned="Principal Architect",
    )

    pill_set = generate_recruiter_replies(message=ctx, calendar_availability=None)
    p1 = next(p for p in pill_set.pills if p.pill_type == RecruiterPillType.ACCEPT_AND_SCHEDULE)
    assert len(p1.calendar_slots_injected) > 0
    assert "Tuesday" in p1.body_text


def test_generate_recruiter_replies_pill_2_scope_and_comp_bounds() -> None:
    ctx = InboundMessageContext(
        message_id="msg-103",
        sender_name="Rachel Green",
        sender_email_or_handle="rachel@startup.ai",
        subject="CTO opportunity",
        body_text="Hey Nate, looking for a CTO.",
        company_mentioned="StartupAI",
        role_mentioned="CTO",
    )

    pill_set = generate_recruiter_replies(message=ctx)
    p2 = next(p for p in pill_set.pills if p.pill_type == RecruiterPillType.REQUEST_SCOPE_AND_COMP)
    assert p2.label == "Request Scope & Comp Details"
    assert "$180k+ base ($250k+ total)" in p2.body_text or "$180k+ base" in p2.body_text
    assert "Technical & organizational scope" in p2.body_text
    assert "Reporting line" in p2.body_text


def test_generate_recruiter_replies_pill_3_polite_pass_preserves_advocacy() -> None:
    ctx = InboundMessageContext(
        message_id="msg-104",
        sender_name="Mark Sloan",
        sender_email_or_handle="mark@agency.io",
        subject="Contract Full Stack Role",
        body_text="Hey Nate, have a 3-month contract role.",
        company_mentioned="AgencyIO",
        role_mentioned="Contract Developer",
    )

    pill_set = generate_recruiter_replies(message=ctx)
    p3 = next(p for p in pill_set.pills if p.pill_type == RecruiterPillType.POLITE_PASS)
    assert p3.label == "Polite Pass"
    assert "stay connected on LinkedIn" in p3.body_text
    assert "refer any exceptional engineering leaders" in p3.body_text
    assert "Nate Walker" in p3.body_text
