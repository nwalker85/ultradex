"""SQLAlchemy row models for disposable job-search projections."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Float, JSON, String

from .models import Base


JOBSEARCH_PROJECTION_TABLES: frozenset[str] = frozenset(
    {
        "jobsearch_opportunities",
        "jobsearch_applications",
        "jobsearch_relationships",
        "jobsearch_outreach",
        "jobsearch_projection_checkpoints",
    }
)

JOBSEARCH_PROJECTION_TYPES: frozenset[str] = frozenset(
    {
        "opportunity",
        "application",
        "relationship",
        "outreach",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityProjectionDB(Base):
    __tablename__ = "jobsearch_opportunities"

    id = Column(String(64), primary_key=True)
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
    source_event_position = Column(BigInteger, nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class ApplicationProjectionDB(Base):
    __tablename__ = "jobsearch_applications"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), nullable=False, index=True)
    state = Column(String(32), nullable=False, index=True)
    stage_history = Column(JSON, nullable=False, default=list)
    artifact_refs = Column(JSON, nullable=False, default=list)
    next_action = Column(String(255), nullable=True)
    next_action_deadline = Column(DateTime(timezone=True), nullable=True)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(BigInteger, nullable=False)
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
    relevance_signals = Column(JSON, nullable=False, default=list)
    source_event_id = Column(String(128), nullable=False)
    source_event_position = Column(BigInteger, nullable=False)
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
    source_event_position = Column(BigInteger, nullable=False)
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
    source_event_position = Column(BigInteger, nullable=False)
    projected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    lag_ms = Column(BigInteger, nullable=False)
    status = Column(String(32), nullable=False, index=True)
