"""Contract-backed reads for disposable job-search projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Generic, Literal, TypeVar

from ravenhelm_contracts import (
    ApplicationV1,
    ExecutionReceiptV1,
    JobSearchIntentV1,
    OpportunityV1,
    OutreachV1,
    ProjectionFreshnessV1,
    RelationshipV1,
)
from ravenhelm_contracts.accountability_v1 import hash_execution_receipt_v1
from ravenhelm_contracts.jobsearch_v1 import (
    APPLICATION_STATUSES_V1,
    DIGEST_PATTERN_V1,
    OPPORTUNITY_STATUSES_V1,
    OUTREACH_CHANNELS_V1,
    OUTREACH_STATUSES_V1,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .jobsearch_models import (
    INTENT_SINGLETON_ID,
    ApplicationProjectionDB,
    IntentProjectionDB,
    JobSearchApprovalDB,
    JobSearchExecutionReceiptDB,
    LeadDB,
    OpportunityProjectionDB,
    OrganizationDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)


T = TypeVar("T")
RowT = TypeVar("RowT")


@dataclass(frozen=True)
class ProjectionPage(Generic[T]):
    """A deterministic page of validated projection contracts."""

    items: tuple[T, ...]
    freshness: ProjectionFreshnessV1 | None
    next_cursor: str | None


@dataclass(frozen=True)
class ProjectedOutreach:
    """A validated outreach item paired with its row-level provenance."""

    item: OutreachV1
    freshness: ProjectionFreshnessV1


@dataclass(frozen=True)
class ApprovalEvidence:
    """Validated evidence for one exact outreach approval mandate."""

    approval_id: str
    outreach_id: str
    message_commitment: str
    channel: str
    approved_by: str
    issued_at: str
    expires_at: str
    status: Literal["approved", "expired", "revoked"]


@dataclass(frozen=True)
class ExecutionReceiptEvidence:
    """A structurally valid receipt recorded by this server.

    Receipt presence and canonical hashing do not establish signature validity.
    Signature verification requires a trusted public-key registry that this read
    surface does not currently provide.
    """

    operation_id: str
    receipt: ExecutionReceiptV1
    receipt_hash: str
    created_at: str
    completed_at: str
    proof_status: Literal["server-recorded"] = "server-recorded"


def _bounded_first(first: int) -> int:
    if isinstance(first, bool) or not isinstance(first, int) or not 1 <= first <= 100:
        raise ValueError("first must be an integer between 1 and 100")
    return first


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _signed_receipt_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError(f"receipt payload {field} must be a timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"receipt payload {field} must include a timezone")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.second != 0 or parsed.microsecond != 0:
        raise ValueError(f"receipt payload {field} must be a whole UTC minute")
    return parsed


def _whole_utc_minute(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _validate_status(
    status: str | None,
    allowed: frozenset[str],
) -> str | None:
    if status is not None and (
        not isinstance(status, str) or status not in allowed
    ):
        raise ValueError("status is not valid for this projection")
    return status


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


class JobSearchProjectionRepository:
    """Read job-search projection rows only through their canonical contracts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_opportunity(self, opportunity_id: str) -> OpportunityV1 | None:
        row = self._session.scalar(
            select(OpportunityProjectionDB).where(
                OpportunityProjectionDB.id == opportunity_id
            )
        )
        if row is None:
            return None
        return self._opportunity(row, self._checkpoint("opportunities"))

    def get_application(self, application_id: str) -> ApplicationV1 | None:
        row = self._session.scalar(
            select(ApplicationProjectionDB).where(
                ApplicationProjectionDB.id == application_id
            )
        )
        if row is None:
            return None
        return self._application(row, self._checkpoint("applications"))

    def get_relationship(self, relationship_id: str) -> RelationshipV1 | None:
        row = self._session.scalar(
            select(RelationshipProjectionDB).where(
                RelationshipProjectionDB.id == relationship_id
            )
        )
        if row is None:
            return None
        return self._relationship(row, self._checkpoint("relationships"))

    def get_outreach(self, outreach_id: str) -> ProjectedOutreach | None:
        row = self._session.scalar(
            select(OutreachProjectionDB).where(
                OutreachProjectionDB.id == outreach_id
            )
        )
        if row is None:
            return None
        return self._outreach(row, self._checkpoint("outreach"))

    def get_intent(self) -> JobSearchIntentV1 | None:
        row = self._session.get(IntentProjectionDB, INTENT_SINGLETON_ID)
        if row is None:
            return None
        return self._intent(row, self._checkpoint("intent"))

    def get_approval(self, approval_id: str) -> ApprovalEvidence | None:
        row = self._session.scalar(
            select(JobSearchApprovalDB).where(
                JobSearchApprovalDB.approval_id == approval_id
            )
        )
        if row is None:
            return None
        return self._approval(row)

    def get_execution_receipt(
        self,
        operation_id: str,
    ) -> ExecutionReceiptEvidence | None:
        row = self._session.scalar(
            select(JobSearchExecutionReceiptDB).where(
                JobSearchExecutionReceiptDB.operation_id == operation_id
            )
        )
        if row is None:
            return None
        return self._execution_receipt(row)

    def get_lead(self, lead_id: str) -> LeadDB | None:
        return self._session.scalar(
            select(LeadDB).where(LeadDB.id == lead_id)
        )

    def list_leads(
        self,
        first: int = 20,
        after: str | None = None,
        min_fit_score: float | None = None,
        state: str | None = None,
        employer: str | None = None,
    ) -> ProjectionPage[LeadDB]:
        limit = _bounded_first(first)
        statement = select(LeadDB)
        if after is not None:
            statement = statement.where(LeadDB.id > after)
        if min_fit_score is not None:
            statement = statement.where(LeadDB.fit_score >= min_fit_score)
        if state is not None:
            statement = statement.where(LeadDB.state == state)
        if employer is not None:
            statement = statement.where(LeadDB.employer == employer)
        statement = statement.order_by(LeadDB.id.asc()).limit(limit + 1)
        rows = list(self._session.scalars(statement))
        freshness = self._checkpoint("leads")
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = page_rows[-1].id if has_next else None
        return ProjectionPage(
            items=tuple(page_rows),
            freshness=freshness,
            next_cursor=next_cursor,
        )

    def get_organization(self, organization_id: str) -> OrganizationDB | None:
        return self._session.scalar(
            select(OrganizationDB).where(OrganizationDB.id == organization_id)
        )

    def list_organizations(
        self,
        first: int = 20,
        after: str | None = None,
        sort_by: str = "name",
    ) -> ProjectionPage[OrganizationDB]:
        limit = _bounded_first(first)
        statement = select(OrganizationDB)
        if after is not None:
            statement = statement.where(OrganizationDB.id > after)
        order_col = OrganizationDB.name if sort_by == "name" else OrganizationDB.id
        statement = statement.order_by(order_col.asc(), OrganizationDB.id.asc()).limit(limit + 1)
        rows = list(self._session.scalars(statement))
        freshness = self._checkpoint("organizations")
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = page_rows[-1].id if has_next else None
        return ProjectionPage(
            items=tuple(page_rows),
            freshness=freshness,
            next_cursor=next_cursor,
        )

    def list_opportunities(
        self,
        first: int,
        after: str | None = None,
        status: str | None = None,
    ) -> ProjectionPage[OpportunityV1]:
        status = _validate_status(status, OPPORTUNITY_STATUSES_V1)
        filters = (
            () if status is None else (OpportunityProjectionDB.state == status,)
        )
        return self._page(
            model=OpportunityProjectionDB,
            projection_type="opportunities",
            first=first,
            after=after,
            filters=filters,
            converter=self._opportunity,
        )

    def list_applications(
        self,
        first: int,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> ProjectionPage[ApplicationV1]:
        status = _validate_status(status, APPLICATION_STATUSES_V1)
        filters = []
        if status is not None:
            filters.append(ApplicationProjectionDB.state == status)
        if opportunity_id is not None:
            filters.append(
                ApplicationProjectionDB.opportunity_id == opportunity_id
            )
        return self._page(
            model=ApplicationProjectionDB,
            projection_type="applications",
            first=first,
            after=after,
            filters=tuple(filters),
            converter=self._application,
        )

    def list_relationships(
        self,
        first: int,
        after: str | None = None,
        opportunity_id: str | None = None,
    ) -> ProjectionPage[RelationshipV1]:
        filters = (
            ()
            if opportunity_id is None
            else (
                RelationshipProjectionDB.opportunity_id == opportunity_id,
            )
        )
        return self._page(
            model=RelationshipProjectionDB,
            projection_type="relationships",
            first=first,
            after=after,
            filters=filters,
            converter=self._relationship,
        )

    def list_outreach(
        self,
        first: int,
        after: str | None = None,
        status: str | None = None,
        opportunity_id: str | None = None,
    ) -> ProjectionPage[ProjectedOutreach]:
        status = _validate_status(status, OUTREACH_STATUSES_V1)
        filters = []
        if status is not None:
            filters.append(OutreachProjectionDB.state == status)
        if opportunity_id is not None:
            filters.append(OutreachProjectionDB.opportunity_id == opportunity_id)
        return self._page(
            model=OutreachProjectionDB,
            projection_type="outreach",
            first=first,
            after=after,
            filters=tuple(filters),
            converter=self._outreach,
        )

    def _page(
        self,
        *,
        model: type[RowT],
        projection_type: str,
        first: int,
        after: str | None,
        filters: tuple[object, ...],
        converter: Callable[
            [RowT, ProjectionFreshnessV1 | None],
            T,
        ],
    ) -> ProjectionPage[T]:
        limit = _bounded_first(first)
        statement = select(model)
        if after is not None:
            statement = statement.where(model.id > after)
        if filters:
            statement = statement.where(*filters)
        statement = statement.order_by(model.id.asc()).limit(limit + 1)
        rows = list(self._session.scalars(statement))
        freshness = self._checkpoint(projection_type)
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        items = tuple(converter(row, freshness) for row in page_rows)
        next_cursor = page_rows[-1].id if has_next else None
        return ProjectionPage(
            items=items,
            freshness=freshness,
            next_cursor=next_cursor,
        )

    def _checkpoint(
        self,
        projection_type: str,
    ) -> ProjectionFreshnessV1 | None:
        row = self._session.scalar(
            select(ProjectionCheckpointDB).where(
                ProjectionCheckpointDB.projection_type == projection_type
            )
        )
        if row is None:
            return None
        return ProjectionFreshnessV1.from_dict(
            {
                "source_event_id": row.source_event_id,
                "source_event_position": row.source_event_position,
                "projected_at": _timestamp(row.projected_at),
                "lag_ms": row.lag_ms,
                "status": row.status,
            }
        )

    @staticmethod
    def _required_freshness(
        row: (
            OpportunityProjectionDB
            | ApplicationProjectionDB
            | RelationshipProjectionDB
            | OutreachProjectionDB
            | IntentProjectionDB
        ),
        freshness: ProjectionFreshnessV1 | None,
    ) -> dict[str, object]:
        """Combine row provenance with checkpoint-scoped lag and health."""
        if freshness is None:
            raise ValueError("projection row has no projection checkpoint")
        return {
            "source_event_id": row.source_event_id,
            "source_event_position": row.source_event_position,
            "projected_at": _timestamp(row.projected_at),
            "lag_ms": freshness.lag_ms,
            "status": freshness.status,
        }

    def _opportunity(
        self,
        row: OpportunityProjectionDB,
        freshness: ProjectionFreshnessV1 | None,
    ) -> OpportunityV1:
        return OpportunityV1.from_dict(
            {
                "opportunity_id": row.id,
                "employer": row.employer_name,
                "title": row.title,
                "location": row.location,
                "role_family": row.role_family,
                "status": row.state,
                "fit_score": row.score,
                "fit_explanation": row.score_explanation,
                "risk_flags": row.risk_flags,
                "evidence_refs": row.evidence_refs,
                "freshness": self._required_freshness(row, freshness),
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
        )

    def _application(
        self,
        row: ApplicationProjectionDB,
        freshness: ProjectionFreshnessV1 | None,
    ) -> ApplicationV1:
        return ApplicationV1.from_dict(
            {
                "application_id": row.id,
                "opportunity_id": row.opportunity_id,
                "status": row.state,
                "stage_history": row.stage_history,
                "artifact_refs": row.artifact_refs,
                "next_action": row.next_action,
                "next_action_at": (
                    None
                    if row.next_action_deadline is None
                    else _timestamp(row.next_action_deadline)
                ),
                "freshness": self._required_freshness(row, freshness),
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
        )

    def _relationship(
        self,
        row: RelationshipProjectionDB,
        freshness: ProjectionFreshnessV1 | None,
    ) -> RelationshipV1:
        return RelationshipV1.from_dict(
            {
                "relationship_id": row.id,
                "opportunity_id": row.opportunity_id,
                "dex_contact_ref": row.dex_contact_ref,
                "relevance_score": row.relevance_score,
                "relevance_summary": row.relevance_reason,
                "freshness": self._required_freshness(row, freshness),
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
        )

    def _outreach(
        self,
        row: OutreachProjectionDB,
        freshness: ProjectionFreshnessV1 | None,
    ) -> ProjectedOutreach:
        return ProjectedOutreach(
            item=OutreachV1.from_dict(
                {
                    "outreach_id": row.id,
                    "opportunity_id": row.opportunity_id,
                    "relationship_id": row.relationship_id,
                    "status": row.state,
                    "channel": row.channel,
                    "message_commitment": row.message_commitment,
                    "approval_contract_id": row.approval_contract_ref,
                    "sent_evidence_ref": row.sent_evidence_ref,
                    "created_at": _timestamp(row.created_at),
                    "updated_at": _timestamp(row.updated_at),
                }
            ),
            freshness=ProjectionFreshnessV1.from_dict(
                self._required_freshness(row, freshness)
            ),
        )

    def _intent(
        self,
        row: IntentProjectionDB,
        freshness: ProjectionFreshnessV1 | None,
    ) -> JobSearchIntentV1:
        return JobSearchIntentV1.from_dict(
            {
                "intent_id": row.id,
                "target_role_families": list(row.target_role_families or []),
                "target_domains": list(row.target_domains or []),
                "seniority_band": row.seniority_band,
                "location_preference": row.location_preference,
                "remote_preference": row.remote_preference,
                "employer_exclusions": list(row.employer_exclusions or []),
                "weights": dict(row.weights or {}),
                "narrative": row.narrative,
                "freshness": self._required_freshness(row, freshness),
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
        )

    @staticmethod
    def _approval(row: JobSearchApprovalDB) -> ApprovalEvidence:
        approval_id = _required_string(row.approval_id, "approval_id")
        outreach_id = _required_string(row.outreach_id, "outreach_id")
        commitment = _required_string(
            row.message_commitment,
            "message_commitment",
        )
        if DIGEST_PATTERN_V1.fullmatch(commitment) is None:
            raise ValueError("message_commitment must be a sha256 commitment")
        channel = _required_string(row.channel, "channel")
        if channel not in OUTREACH_CHANNELS_V1:
            raise ValueError("channel is not valid for outreach approval")
        approved_by = _required_string(row.approved_by, "approved_by")
        status = _required_string(row.status, "status")
        if status not in {"approved", "expired", "revoked"}:
            raise ValueError("status is not valid for outreach approval")
        issued_at = row.issued_at
        expires_at = row.expires_at
        if issued_at is None or expires_at is None or expires_at <= issued_at:
            raise ValueError("approval expiry must follow issuance")
        return ApprovalEvidence(
            approval_id=approval_id,
            outreach_id=outreach_id,
            message_commitment=commitment,
            channel=channel,
            approved_by=approved_by,
            issued_at=_timestamp(issued_at),
            expires_at=_timestamp(expires_at),
            status=status,  # type: ignore[arg-type]
        )

    @staticmethod
    def _execution_receipt(
        row: JobSearchExecutionReceiptDB,
    ) -> ExecutionReceiptEvidence:
        operation_id = _required_string(row.operation_id, "operation_id")
        receipt = ExecutionReceiptV1.from_dict(row.payload)
        if receipt.receipt_id != row.receipt_id:
            raise ValueError("receipt payload does not match receipt_id")
        if receipt.event_id != row.event_id:
            raise ValueError("receipt payload does not match event_id")
        if receipt.status != row.status:
            raise ValueError("receipt payload does not match status")
        if receipt.reason_code != row.reason_code:
            raise ValueError("receipt payload does not match reason_code")
        receipt_hash = hash_execution_receipt_v1(receipt)
        if receipt_hash != row.receipt_hash:
            raise ValueError("receipt payload does not match receipt_hash")
        signed_completed_at = _signed_receipt_timestamp(
            receipt.completed_at,
            "completed_at",
        )
        if _whole_utc_minute(row.completed_at) != signed_completed_at:
            raise ValueError(
                "receipt row completed_at does not match signed payload"
            )
        return ExecutionReceiptEvidence(
            operation_id=operation_id,
            receipt=receipt,
            receipt_hash=receipt_hash,
            created_at=_timestamp(row.created_at),
            completed_at=_timestamp(signed_completed_at),
        )


def get_lead(db: Session, lead_id: str) -> LeadDB | None:
    """Read a single lead projection by ID."""
    return JobSearchProjectionRepository(db).get_lead(lead_id)


def list_leads(
    db: Session,
    first: int = 20,
    after: str | None = None,
    min_fit_score: float | None = None,
    state: str | None = None,
    employer: str | None = None,
) -> ProjectionPage[LeadDB]:
    """Read a page of lead projections with optional filtering."""
    return JobSearchProjectionRepository(db).list_leads(
        first=first,
        after=after,
        min_fit_score=min_fit_score,
        state=state,
        employer=employer,
    )


def get_organization(db: Session, organization_id: str) -> OrganizationDB | None:
    """Read a single organization projection by ID."""
    return JobSearchProjectionRepository(db).get_organization(organization_id)


def list_organizations(
    db: Session,
    first: int = 20,
    after: str | None = None,
    sort_by: str = "name",
) -> ProjectionPage[OrganizationDB]:
    """Read a page of organization projections."""
    return JobSearchProjectionRepository(db).list_organizations(
        first=first,
        after=after,
        sort_by=sort_by,
    )
