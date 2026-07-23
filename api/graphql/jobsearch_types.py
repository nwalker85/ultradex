"""Explicit GraphQL types for canonical job-search read projections."""

from __future__ import annotations

from datetime import datetime

import strawberry
from ravenhelm_contracts import (
    ApplicationStageV1,
    ApplicationV1,
    JobSearchEvidenceReferenceV1,
    OpportunityV1,
    OutreachV1,
    ProjectionFreshnessV1,
    RelationshipV1,
)

from core import ProjectionPage


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@strawberry.type
class EvidenceReference:
    evidence_id: str
    source_kind: str
    source_ref: str
    classification: str
    observed_at: datetime
    commitment: str
    redacted_summary: str

    @classmethod
    def from_contract(
        cls,
        contract: JobSearchEvidenceReferenceV1,
    ) -> "EvidenceReference":
        return cls(
            evidence_id=contract.evidence_id,
            source_kind=contract.source_kind,
            source_ref=contract.source_ref,
            classification=contract.classification,
            observed_at=_datetime(contract.observed_at),
            commitment=contract.commitment,
            redacted_summary=contract.redacted_summary,
        )


@strawberry.type
class ProjectionFreshness:
    source_event_id: str
    source_event_position: str
    projected_at: datetime
    lag_ms: float
    status: str

    @classmethod
    def from_contract(
        cls,
        contract: ProjectionFreshnessV1,
    ) -> "ProjectionFreshness":
        return cls(
            source_event_id=contract.source_event_id,
            source_event_position=contract.source_event_position,
            projected_at=_datetime(contract.projected_at),
            lag_ms=float(contract.lag_ms),
            status=contract.status,
        )


@strawberry.type
class ApplicationStage:
    status: str
    occurred_at: datetime
    evidence_ref: str | None

    @classmethod
    def from_contract(cls, contract: ApplicationStageV1) -> "ApplicationStage":
        return cls(
            status=contract.status,
            occurred_at=_datetime(contract.occurred_at),
            evidence_ref=contract.evidence_ref,
        )


@strawberry.type
class Opportunity:
    opportunity_id: str
    employer: str
    title: str
    location: str | None
    role_family: str | None
    status: str
    fit_score: float | None
    fit_explanation: str | None
    risk_flags: list[str]
    evidence_refs: list[EvidenceReference]
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: OpportunityV1) -> "Opportunity":
        return cls(
            opportunity_id=contract.opportunity_id,
            employer=contract.employer,
            title=contract.title,
            location=contract.location,
            role_family=contract.role_family,
            status=contract.status,
            fit_score=(
                None if contract.fit_score is None else float(contract.fit_score)
            ),
            fit_explanation=contract.fit_explanation,
            risk_flags=list(contract.risk_flags),
            evidence_refs=[
                EvidenceReference.from_contract(item)
                for item in contract.evidence_refs
            ],
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class Application:
    application_id: str
    opportunity_id: str
    status: str
    stage_history: list[ApplicationStage]
    artifact_refs: list[str]
    next_action: str | None
    next_action_at: datetime | None
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: ApplicationV1) -> "Application":
        return cls(
            application_id=contract.application_id,
            opportunity_id=contract.opportunity_id,
            status=contract.status,
            stage_history=[
                ApplicationStage.from_contract(stage)
                for stage in contract.stage_history
            ],
            artifact_refs=list(contract.artifact_refs),
            next_action=contract.next_action,
            next_action_at=(
                None
                if contract.next_action_at is None
                else _datetime(contract.next_action_at)
            ),
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class Relationship:
    relationship_id: str
    opportunity_id: str
    dex_contact_ref: str
    relevance_score: float | None
    relevance_summary: str | None
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: RelationshipV1) -> "Relationship":
        return cls(
            relationship_id=contract.relationship_id,
            opportunity_id=contract.opportunity_id,
            dex_contact_ref=contract.dex_contact_ref,
            relevance_score=(
                None
                if contract.relevance_score is None
                else float(contract.relevance_score)
            ),
            relevance_summary=contract.relevance_summary,
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class Outreach:
    outreach_id: str
    opportunity_id: str
    relationship_id: str | None
    status: str
    channel: str
    message_commitment: str
    approval_contract_id: str | None
    sent_evidence_ref: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: OutreachV1) -> "Outreach":
        return cls(
            outreach_id=contract.outreach_id,
            opportunity_id=contract.opportunity_id,
            relationship_id=contract.relationship_id,
            status=contract.status,
            channel=contract.channel,
            message_commitment=contract.message_commitment,
            approval_contract_id=contract.approval_contract_id,
            sent_evidence_ref=contract.sent_evidence_ref,
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class OpportunityPage:
    items: list[Opportunity]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[OpportunityV1],
    ) -> "OpportunityPage":
        return cls(
            items=[Opportunity.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class ApplicationPage:
    items: list[Application]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[ApplicationV1],
    ) -> "ApplicationPage":
        return cls(
            items=[Application.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class RelationshipPage:
    items: list[Relationship]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[RelationshipV1],
    ) -> "RelationshipPage":
        return cls(
            items=[Relationship.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class OutreachPage:
    items: list[Outreach]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[OutreachV1],
    ) -> "OutreachPage":
        return cls(
            items=[Outreach.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )
