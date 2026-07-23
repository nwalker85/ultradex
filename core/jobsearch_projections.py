"""Contract-backed reads for disposable job-search projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Generic, TypeVar

from ravenhelm_contracts import (
    ApplicationV1,
    OpportunityV1,
    OutreachV1,
    ProjectionFreshnessV1,
    RelationshipV1,
)
from ravenhelm_contracts.jobsearch_v1 import (
    APPLICATION_STATUSES_V1,
    OPPORTUNITY_STATUSES_V1,
    OUTREACH_STATUSES_V1,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .jobsearch_models import (
    ApplicationProjectionDB,
    OpportunityProjectionDB,
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


def _bounded_first(first: int) -> int:
    if isinstance(first, bool) or not isinstance(first, int) or not 1 <= first <= 100:
        raise ValueError("first must be an integer between 1 and 100")
    return first


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_status(
    status: str | None,
    allowed: frozenset[str],
) -> str | None:
    if status is not None and (
        not isinstance(status, str) or status not in allowed
    ):
        raise ValueError("status is not valid for this projection")
    return status


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
