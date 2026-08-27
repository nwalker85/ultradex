"""SQLAlchemy row models for disposable job-search projections."""

from datetime import datetime, timezone

from ravenhelm_contracts.jobsearch_v1 import JOBSEARCH_PROJECTION_TYPES_V1
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .models import Base


JOBSEARCH_PROJECTION_TABLES: frozenset[str] = frozenset(
    {
        "jobsearch_opportunities",
        "jobsearch_applications",
        "jobsearch_relationships",
        "jobsearch_outreach",
        "jobsearch_intent",
        "jobsearch_projection_checkpoints",
        "jobsearch_organizations",
        "jobsearch_leads",
    }
)

# Fixed identifiers for the two workspace-scoped singleton rows (CCC Wave 2,
# Lane F1). `intent.set` and `workspace.initialize` are replace-style: they
# always mutate the one private-workspace row rather than taking an
# identifier, per the ravenhelm-contracts jobsearch.v1 README.
INTENT_SINGLETON_ID: str = "intent-workspace-01"
WORKSPACE_SINGLETON_ID: str = "workspace-private"

JOBSEARCH_COMMAND_TABLES: frozenset[str] = frozenset(
    {
        "jobsearch_commands",
        "jobsearch_evidence_refs",
        "jobsearch_approvals",
        "jobsearch_lifecycle_events",
        "jobsearch_execution_receipts",
    }
)

JOBSEARCH_ANNOTATION_TABLES: frozenset[str] = frozenset(
    {
        "jobsearch_entity_notes",
    }
)

JOBSEARCH_VERSIONED_TABLES: frozenset[str] = (
    JOBSEARCH_PROJECTION_TABLES
    | JOBSEARCH_COMMAND_TABLES
    | JOBSEARCH_ANNOTATION_TABLES
)

JOBSEARCH_PROJECTION_TYPES: frozenset[str] = JOBSEARCH_PROJECTION_TYPES_V1

ENTITY_NOTE_TYPES: frozenset[str] = frozenset(
    {
        "contact",
        "organization",
        "relationship",
        "opportunity",
        "application",
        "lead",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityProjectionDB(Base):
    __tablename__ = "jobsearch_opportunities"

    id = Column(String(64), primary_key=True)
    organization_id = Column(
        String(64),
        ForeignKey("jobsearch_organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    employer_name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    role_family = Column(String(128), nullable=True)
    state = Column(String(32), nullable=False, index=True)
    score = Column(Float, nullable=True)
    score_explanation = Column(String(1000), nullable=True)
    risk_flags = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=list)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    organization = relationship(
        "OrganizationDB",
        back_populates="opportunities",
        foreign_keys=[organization_id],
    )


class ApplicationProjectionDB(Base):
    __tablename__ = "jobsearch_applications"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    state = Column(String(32), nullable=False, index=True)
    stage_history = Column(JSON, nullable=False, default=list)
    artifact_refs = Column(JSON, nullable=False, default=list)
    next_action = Column(String(500), nullable=True)
    next_action_deadline = Column(DateTime(timezone=True), nullable=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class RelationshipProjectionDB(Base):
    __tablename__ = "jobsearch_relationships"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    dex_contact_ref = Column(String(255), nullable=False)
    relevance_score = Column(Float, nullable=True)
    relevance_reason = Column(String(500), nullable=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class OutreachProjectionDB(Base):
    __tablename__ = "jobsearch_outreach"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    relationship_id = Column(String(64), nullable=True, index=True)
    state = Column(String(32), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    message_commitment = Column(String(255), nullable=False)
    approval_contract_ref = Column(String(255), nullable=True)
    sent_evidence_ref = Column(String(255), nullable=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class IntentProjectionDB(Base):
    """The single workspace-scoped `JobSearchIntentV1` targeting record.

    Replace-style singleton: exactly one row, keyed by `INTENT_SINGLETON_ID`,
    always rewritten in place by `intent.set` rather than appended to.
    """

    __tablename__ = "jobsearch_intent"

    id = Column(String(64), primary_key=True)
    target_role_families = Column(JSON, nullable=False, default=list)
    target_domains = Column(JSON, nullable=False, default=list)
    seniority_band = Column(String(128), nullable=False)
    location_preference = Column(String(255), nullable=True)
    remote_preference = Column(String(32), nullable=False)
    employer_exclusions = Column(JSON, nullable=False, default=list)
    weights = Column(JSON, nullable=False)
    narrative = Column(String(2000), nullable=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class ProjectionCheckpointDB(Base):
    __tablename__ = "jobsearch_projection_checkpoints"

    projection_type = Column(String(32), primary_key=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(String(128), nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    lag_ms = Column(BigInteger, nullable=False)
    status = Column(String(32), nullable=False, index=True)


class OrganizationDB(Base):
    """Employer organization directory aggregating contacts, leads, and pipeline pursuits."""

    __tablename__ = "jobsearch_organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)
    industry = Column(String(128), nullable=True, index=True)
    size = Column(String(64), nullable=True)
    advocacy_rating = Column(Float, nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # Freshness and audit metadata
    source_event_id = Column(String(128), nullable=False, default="pending")
    source_event_position = Column(String(128), nullable=False, default="pending")
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ORM Relationships
    leads = relationship(
        "LeadDB",
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="LeadDB.organization_id",
    )
    contacts = relationship(
        "ContactDB",
        back_populates="organization",
        foreign_keys="ContactDB.organization_id",
    )
    opportunities = relationship(
        "OpportunityProjectionDB",
        back_populates="organization",
        foreign_keys="OpportunityProjectionDB.organization_id",
    )


class LeadDB(Base):
    """Unapplied job posting with profile match breakdown, risk flags, and conversion tracking."""

    __tablename__ = "jobsearch_leads"

    id = Column(String(64), primary_key=True)
    source_board = Column(String(64), nullable=False, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    employer = Column(String(255), nullable=False, index=True)
    organization_id = Column(
        String(64),
        ForeignKey("jobsearch_organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    remote_type = Column(String(32), nullable=False, default="unknown", index=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(8), nullable=False, default="USD")
    url = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=False, default=list)
    fit_score = Column(Float, nullable=True, index=True)
    match_breakdown = Column(JSON, nullable=False, default=dict)
    risk_flags = Column(JSON, nullable=False, default=list)
    state = Column(String(32), nullable=False, default="discovered", index=True)
    converted_opportunity_id = Column(
        String(64),
        ForeignKey("jobsearch_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Freshness and audit metadata
    source_event_id = Column(String(128), nullable=False, default="pending")
    source_event_position = Column(String(128), nullable=False, default="pending")
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ORM Relationships
    organization = relationship(
        "OrganizationDB",
        back_populates="leads",
        foreign_keys=[organization_id],
    )
    converted_opportunity = relationship(
        "OpportunityProjectionDB",
        foreign_keys=[converted_opportunity_id],
    )


class JobSearchCommandDB(Base):
    """Durable private record of one accepted canonical command."""

    __tablename__ = "jobsearch_commands"

    operation_id = Column(String(36), primary_key=True)
    command_id = Column(String(128), nullable=False, unique=True)
    command_name = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(128), nullable=False)
    delegation_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(255), nullable=False)
    context = Column(JSON, nullable=False)
    parameters = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    dispatched_at = Column(DateTime(timezone=True), nullable=True, index=True)


class JobSearchEvidenceReferenceDB(Base):
    """Normalized evidence metadata; raw source content stays in source custody."""

    __tablename__ = "jobsearch_evidence_refs"

    evidence_id = Column(String(128), primary_key=True)
    source_kind = Column(String(32), nullable=False, index=True)
    source_ref = Column(String(255), nullable=False)
    classification = Column(String(32), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    commitment = Column(String(71), nullable=False)
    redacted_summary = Column(String(240), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class JobSearchApprovalDB(Base):
    """Approval evidence bound to one outreach commitment and channel."""

    __tablename__ = "jobsearch_approvals"

    approval_id = Column(String(128), primary_key=True)
    outreach_id = Column(String(64), nullable=False, index=True)
    message_commitment = Column(String(71), nullable=False)
    channel = Column(String(32), nullable=False)
    approved_by = Column(String(128), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)


class JobSearchLifecycleEventDB(Base):
    """Canonical job-search event and its JetStream publication state."""

    __tablename__ = "jobsearch_lifecycle_events"

    event_id = Column(String(128), primary_key=True)
    operation_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)


class JobSearchExecutionReceiptDB(Base):
    """One terminal accountability receipt per accepted operation."""

    __tablename__ = "jobsearch_execution_receipts"

    receipt_id = Column(String(128), primary_key=True)
    operation_id = Column(String(36), nullable=False, unique=True, index=True)
    event_id = Column(String(128), nullable=False, unique=True)
    status = Column(String(32), nullable=False, index=True)
    reason_code = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False)
    receipt_hash = Column(String(71), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=False)


class EntityNoteDB(Base):
    """Operator-authored note attached to a CRM entity."""

    __tablename__ = "jobsearch_entity_notes"

    id = Column(String(64), primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    submitted_by = Column(String(255), nullable=False)
    category = Column(String(128), nullable=True)
    disposition = Column(String(128), nullable=True)
    assigned_to = Column(String(255), nullable=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
