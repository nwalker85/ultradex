"""GraphQL schema for Ultradex"""

from datetime import datetime, timezone
import os
from typing import Optional, List
import uuid
import strawberry
from fastapi import Depends
from strawberry.scalars import JSON
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core import (
    JobSearchProjectionRepository,
    OperationDB,
    OperationEventDB,
    get_db,
)
from api.auth import AuthenticatedPrincipal, require_read_principal
from .jobsearch_types import (
    ApprovalEvidence,
    Application,
    ApplicationPage,
    ExecutionReceiptEvidence,
    Opportunity,
    OpportunityPage,
    Outreach,
    OutreachPage,
    Relationship,
    RelationshipPage,
    CandidateProfileGQL,
    Lead,
    LeadPage,
    Organization,
    OrganizationPage,
    ContactGQL,
    ContactPageGQL,
    NextBestActionGQL,
    InboundMessageContextInput,
    RecruiterPillSetGQL,
    CalendarEventGQL,
    DailyAvailabilityGQL,
    MessageGQL,
    MessagePageGQL,
    InterviewDebriefGQL,
    InterviewDebriefPageGQL,
)


def _as_utc(value: datetime | None) -> datetime | None:
    """Coerce DB naive timestamps to UTC-aware for RFC 3339 GraphQL serialization.

    `operations.*` columns are `timestamp without time zone`. Strawberry emits
    naive values without an offset, which fails the Obsidian SDK isoTimestamp
    contract (requires Z or ±HH:MM). Treat naive rows as UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_graphql_context(
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
) -> dict[str, object]:
    """Provide the read-only GraphQL projection session."""
    return {"db": db, "principal": principal}


@strawberry.type
class OperationEventGQL:
    """GraphQL type for OperationEvent"""
    id: int
    operation_id: str
    event_type: str
    timestamp: datetime
    payload: Optional[JSON] = None


@strawberry.type
class ProjectionFreshnessGQL:
    """Freshness metadata for a read projection."""

    source_event_id: str
    source_event_position: str
    projected_at: datetime
    lag_ms: float
    status: str


@strawberry.type
class OperationGQL:
    """GraphQL type for Operation"""
    id: str
    correlation_id: Optional[str]
    command: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[JSON]
    error: Optional[str]
    freshness: Optional[ProjectionFreshnessGQL]

    @classmethod
    def from_db(cls, op: OperationDB) -> "OperationGQL":
        """Convert OperationDB to GraphQL type"""
        return cls(
            id=op.id,
            correlation_id=op.correlation_id,
            command=op.command,
            status=op.status,
            created_at=_as_utc(op.created_at),
            started_at=_as_utc(op.started_at),
            completed_at=_as_utc(op.completed_at),
            result=op.result,
            error=(None if op.error is None or op.error.strip() == "" else op.error),
            # U01 has no durable projector checkpoint. Null is more truthful
            # than manufacturing a zero-lag/fresh projection at request time.
            freshness=None,
        )


@strawberry.type
class Query:
    """GraphQL query root"""

    # -----------------------------------------------------------------------
    # Opportunities, Applications, Relationships, Outreach, Operations
    # -----------------------------------------------------------------------
    @strawberry.field
    def opportunity(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Opportunity | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_opportunity(id)
        return (
            None
            if projection is None
            else Opportunity.from_contract(projection)
        )

    @strawberry.field
    def opportunities(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
    ) -> OpportunityPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_opportunities(
            first=first,
            after=after,
            status=status,
        )
        return OpportunityPage.from_page(page)

    @strawberry.field
    def application(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Application | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_application(id)
        return (
            None
            if projection is None
            else Application.from_contract(projection)
        )

    @strawberry.field
    def applications(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> ApplicationPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_applications(
            first=first,
            after=after,
            status=status,
            opportunity_id=opportunity_id,
        )
        return ApplicationPage.from_page(page)

    @strawberry.field
    def relationship(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Relationship | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_relationship(id)
        return (
            None
            if projection is None
            else Relationship.from_contract(projection)
        )

    @strawberry.field
    def relationships(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        opportunity_id: str | None = None,
    ) -> RelationshipPage:
        page = JobSearchProjectionRepository(
            info.context["db"]
        ).list_relationships(
            first=first,
            after=after,
            opportunity_id=opportunity_id,
        )
        return RelationshipPage.from_page(page)

    @strawberry.field
    def outreach_item(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Outreach | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_outreach(id)
        return (
            None
            if projection is None
            else Outreach.from_projection(projection)
        )

    @strawberry.field
    def outreach(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> OutreachPage:
        page = JobSearchProjectionRepository(info.context["db"]).list_outreach(
            first=first,
            after=after,
            status=status,
            opportunity_id=opportunity_id,
        )
        return OutreachPage.from_page(page)

    @strawberry.field
    def approval(
        self,
        info: strawberry.Info,
        id: str,
    ) -> ApprovalEvidence | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_approval(id)
        return (
            None
            if projection is None
            else ApprovalEvidence.from_projection(projection)
        )

    @strawberry.field
    def execution_receipt(
        self,
        info: strawberry.Info,
        operation_id: str,
    ) -> ExecutionReceiptEvidence | None:
        projection = JobSearchProjectionRepository(
            info.context["db"]
        ).get_execution_receipt(operation_id)
        return (
            None
            if projection is None
            else ExecutionReceiptEvidence.from_projection(projection)
        )

    @strawberry.field
    def operation(self, info: strawberry.Info, id: str) -> Optional[OperationGQL]:
        """Get a single operation by ID"""
        db: Session = info.context["db"]
        op = db.query(OperationDB).filter(OperationDB.id == id).first()
        if not op:
            return None
        return OperationGQL.from_db(op)

    @strawberry.field
    def operations(
        self,
        info: strawberry.Info,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[OperationGQL]:
        """List operations with optional filtering"""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        db: Session = info.context["db"]
        query = db.query(OperationDB).order_by(OperationDB.created_at.desc())
        if status:
            query = query.filter(OperationDB.status == status)
        ops = query.limit(limit).all()
        return [OperationGQL.from_db(op) for op in ops]

    @strawberry.field
    def events(
        self,
        info: strawberry.Info,
        operation_id: str,
        first: int = 50,
        after: Optional[int] = None,
    ) -> List[OperationEventGQL]:
        """Get one stable, bounded page of lifecycle events."""
        if not 1 <= first <= 100:
            raise ValueError("first must be between 1 and 100")
        db: Session = info.context["db"]
        query = db.query(OperationEventDB).filter(
            OperationEventDB.operation_id == operation_id
        )
        if after is not None:
            cursor = db.query(OperationEventDB).filter(
                OperationEventDB.id == after,
                OperationEventDB.operation_id == operation_id,
            ).first()
            if cursor is None:
                raise ValueError("after cursor does not exist for operation")
            query = query.filter(
                or_(
                    OperationEventDB.timestamp > cursor.timestamp,
                    and_(
                        OperationEventDB.timestamp == cursor.timestamp,
                        OperationEventDB.id > cursor.id,
                    ),
                )
            )
        events = query.order_by(
            OperationEventDB.timestamp.asc(),
            OperationEventDB.id.asc(),
        ).limit(first).all()
        return [
            OperationEventGQL(
                id=e.id,
                operation_id=e.operation_id,
                event_type=e.event_type,
                timestamp=_as_utc(e.timestamp),
                payload=e.payload
            )
            for e in events
        ]

    # -----------------------------------------------------------------------
    # Candidate Profile
    # -----------------------------------------------------------------------
    @strawberry.field
    def profile(self, info: strawberry.Info) -> CandidateProfileGQL:
        """Fetch the authoritative Candidate Profile with 44 CTO skills and ML depth."""
        db: Session = info.context["db"]
        from core.jobsearch_profile import CandidateProfileStore
        store = CandidateProfileStore(db)
        prof = store.get_profile()
        return CandidateProfileGQL.from_pydantic(prof)

    # -----------------------------------------------------------------------
    # Leads & Organizations
    # -----------------------------------------------------------------------
    @strawberry.field
    def lead(self, info: strawberry.Info, id: str) -> Optional[Lead]:
        """Fetch a single unapplied job lead projection by ID."""
        db: Session = info.context["db"]
        repo = JobSearchProjectionRepository(db)
        row = repo.get_lead(id)
        if row is None:
            return None
        checkpoint = repo._checkpoint("leads")
        return Lead.from_db(row, checkpoint)

    @strawberry.field
    def leads(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        min_fit_score: Optional[float] = None,
        state: Optional[str] = None,
        employer: Optional[str] = None,
    ) -> LeadPage:
        """List unapplied job leads with fit scores, breakdown, and filtering."""
        db: Session = info.context["db"]
        page = JobSearchProjectionRepository(db).list_leads(
            first=first,
            after=after,
            min_fit_score=min_fit_score,
            state=state,
            employer=employer,
        )
        return LeadPage.from_page(page)

    @strawberry.field
    def organization(self, info: strawberry.Info, id: str) -> Optional[Organization]:
        """Fetch a single employer organization by ID."""
        db: Session = info.context["db"]
        repo = JobSearchProjectionRepository(db)
        row = repo.get_organization(id)
        if row is None:
            return None
        checkpoint = repo._checkpoint("organizations")
        return Organization.from_db(row, checkpoint)

    @strawberry.field
    def organizations(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        sort_by: str = "name",
    ) -> OrganizationPage:
        """List employer directory with advocacy ratings and firmographics."""
        db: Session = info.context["db"]
        page = JobSearchProjectionRepository(db).list_organizations(
            first=first,
            after=after,
            sort_by=sort_by,
        )
        return OrganizationPage.from_page(page)

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------
    @strawberry.field
    def contact(self, info: strawberry.Info, id: str) -> Optional[ContactGQL]:
        """Fetch a Dex contact with advocacy score and communication history."""
        db: Session = info.context["db"]
        from core.dex_client import enrich_contact_from_dex
        row = enrich_contact_from_dex(db, id)
        if row is None:
            return None
        return ContactGQL.from_db(row)

    @strawberry.field
    def contacts(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        organization_id: Optional[str] = None,
        min_advocacy_score: Optional[float] = None,
        relationship_tier: Optional[str] = None,
        search: Optional[str] = None,
    ) -> ContactPageGQL:
        """List Dex contacts with filtering and cursor pagination."""
        if not 1 <= first <= 100:
            raise ValueError("first must be between 1 and 100")
        db: Session = info.context["db"]
        from core.models import ContactDB
        stmt = select(ContactDB)
        if after is not None:
            stmt = stmt.where(ContactDB.id > after)
        if organization_id is not None:
            stmt = stmt.where(ContactDB.organization_id == organization_id)
        if min_advocacy_score is not None:
            stmt = stmt.where(ContactDB.advocacy_score >= min_advocacy_score)
        if relationship_tier is not None:
            stmt = stmt.where(ContactDB.relationship_tier == relationship_tier)
        if search is not None and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ContactDB.name.ilike(term),
                    ContactDB.company.ilike(term),
                    ContactDB.job_title.ilike(term),
                    ContactDB.email.ilike(term),
                )
            )
        stmt = stmt.order_by(ContactDB.id.asc()).limit(first + 1)
        rows = list(db.scalars(stmt))
        has_next = len(rows) > first
        page_rows = rows[:first]
        next_cursor = page_rows[-1].id if has_next else None
        return ContactPageGQL(
            items=[ContactGQL.from_db(r) for r in page_rows],
            freshness=None,
            next_cursor=next_cursor,
        )

    # -----------------------------------------------------------------------
    # Copilot Next Best Actions & Recruiter Replies
    # -----------------------------------------------------------------------
    @strawberry.field
    def next_best_actions(
        self,
        info: strawberry.Info,
        limit: int = 10,
    ) -> list[NextBestActionGQL]:
        """Compute prioritized Next Best Actions for the Command Home rail."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        db: Session = info.context["db"]
        from core.jobsearch_copilot import JobSearchCopilot
        copilot = JobSearchCopilot(db=db)
        nbas = copilot.compute_next_best_actions(limit=limit)
        return [NextBestActionGQL.from_pydantic(nba) for nba in nbas]

    @strawberry.field
    def generate_recruiter_replies(
        self,
        info: strawberry.Info,
        message: Optional[InboundMessageContextInput] = None,
        message_context: Optional[InboundMessageContextInput] = None,
        calendar_availability: Optional[list[str]] = None,
    ) -> RecruiterPillSetGQL:
        """Generate 3 contextual recruiter response pills with live calendar slots."""
        msg_input = message or message_context
        if msg_input is None:
            raise ValueError("message or message_context is required")
        db: Session = info.context["db"]
        from core.jobsearch_copilot import JobSearchCopilot
        copilot = JobSearchCopilot(db=db)
        sender_email = msg_input.sender_email or msg_input.sender_email_or_handle or "recruiter@example.com"
        ctx = copilot.extract_message_context(
            subject=msg_input.subject,
            body=msg_input.body_text,
            sender_email=sender_email,
            sender_name=msg_input.sender_name or "Recruiter",
            message_id=msg_input.message_id or f"msg-{uuid.uuid4()}",
            channel=msg_input.channel or "gmail",
        )
        if msg_input.company_mentioned:
            ctx.company_mentioned = msg_input.company_mentioned
        if msg_input.role_mentioned:
            ctx.role_mentioned = msg_input.role_mentioned
        slots = calendar_availability or msg_input.calendar_slots
        pill_set = copilot.generate_recruiter_replies(
            message=ctx,
            calendar_availability=slots,
        )
        return RecruiterPillSetGQL.from_pydantic(pill_set)

    # -----------------------------------------------------------------------
    # Calendar & Availability
    # -----------------------------------------------------------------------
    @strawberry.field
    def calendar_events(
        self,
        info: strawberry.Info,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
    ) -> list[CalendarEventGQL]:
        """Retrieve Google Calendar sensed events."""
        from core.jobsearch_calendar import (
            GoogleCalendarClient,
            resolve_calendar_access_token,
        )
        try:
            token = resolve_calendar_access_token()
            client = GoogleCalendarClient()
            events = client.fetch_events(access_token=token)
            return [CalendarEventGQL.from_pydantic(e) for e in events]
        except Exception:
            return []

    @strawberry.field
    def availability(
        self,
        info: strawberry.Info,
        start_date: str,
        end_date: str,
        duration_minutes: int = 30,
        buffer_minutes: int = 15,
    ) -> list[DailyAvailabilityGQL]:
        """Compute open Central Time working hours (09:00–17:00 CT) interview slots."""
        from datetime import date as dt_date
        from core.jobsearch_calendar import (
            GoogleCalendarClient,
            compute_daily_availability,
            resolve_calendar_access_token,
        )
        s_date = dt_date.fromisoformat(start_date)
        e_date = dt_date.fromisoformat(end_date)
        events = []
        try:
            token = resolve_calendar_access_token()
            client = GoogleCalendarClient()
            events = client.fetch_events(access_token=token)
        except Exception:
            events = []

        daily = compute_daily_availability(
            events=events,
            start_date=s_date,
            end_date=e_date,
            buffer_minutes=buffer_minutes,
        )
        return [DailyAvailabilityGQL.from_pydantic(d) for d in daily]

    # -----------------------------------------------------------------------
    # Messages
    # -----------------------------------------------------------------------
    @strawberry.field
    def messages(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        thread_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> MessagePageGQL:
        """Retrieve omnichannel outbox messages."""
        db: Session = info.context["db"]
        from core.jobsearch_models import OutreachProjectionDB
        from core.jobsearch_messaging import MessageChannel, MessageStatus, OutboxMessage
        stmt = select(OutreachProjectionDB)
        if status:
            stmt = stmt.where(OutreachProjectionDB.state == status)
        if channel:
            stmt = stmt.where(OutreachProjectionDB.channel == channel)
        if after:
            stmt = stmt.where(OutreachProjectionDB.id > after)
        stmt = stmt.order_by(OutreachProjectionDB.id.asc()).limit(first + 1)
        rows = list(db.scalars(stmt))
        has_next = len(rows) > first
        page_rows = rows[:first]
        next_cursor = page_rows[-1].id if has_next else None

        results = []
        for r in page_rows:
            chan = MessageChannel.GMAIL if r.channel == "gmail" else (MessageChannel.LINKEDIN if r.channel == "linkedin" else MessageChannel.DEX)
            stat = MessageStatus.PENDING_APPROVAL if r.state == "pending_approval" else (MessageStatus.APPROVED if r.state == "approved" else MessageStatus.DRAFT)
            msg = OutboxMessage(
                id=r.id,
                channel=chan,
                recipient_address=r.relationship_id or "",
                subject=f"Outreach for {r.opportunity_id}",
                body_text=f"Commitment: {r.message_commitment}",
                status=stat,
                message_commitment=r.message_commitment or "",
                approval_id=r.approval_contract_ref,
                sent_evidence_ref=r.sent_evidence_ref,
                created_at=r.created_at,
            )
            results.append(MessageGQL.from_pydantic(msg))
        return MessagePageGQL(items=results, freshness=None, next_cursor=next_cursor)

    # -----------------------------------------------------------------------
    # Sovereign Voice & Interview Debriefs
    # -----------------------------------------------------------------------
    @strawberry.field
    def interview_debrief(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Optional[InterviewDebriefGQL]:
        """Retrieve a structured interview debrief by ID."""
        from core.jobsearch_gjallarhorn import get_debrief
        debrief = get_debrief(id)
        if debrief is None:
            return None
        return InterviewDebriefGQL.from_pydantic(debrief)

    @strawberry.field
    def interview_debriefs(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        opportunity_id: Optional[str] = None,
    ) -> InterviewDebriefPageGQL:
        """List structured interview debriefs optionally filtered by opportunity ID."""
        from core.jobsearch_gjallarhorn import list_debriefs
        debriefs = list_debriefs(opportunity_id=opportunity_id, first=first)
        return InterviewDebriefPageGQL(
            items=[InterviewDebriefGQL.from_pydantic(d) for d in debriefs],
            freshness=None,
            next_cursor=None,
        )


schema = strawberry.Schema(query=Query)
