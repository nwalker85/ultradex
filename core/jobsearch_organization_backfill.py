"""Backfill employer directory rows from existing pipeline data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import ContactDB
from core.jobsearch_models import LeadDB, OpportunityProjectionDB, OrganizationDB
from core.jobsearch_organization_resolve import (
    _normalize_employer,
    find_organization_for_employer,
)


@dataclass(frozen=True)
class OrganizationBackfillResult:
    """Summary of one backfill run."""

    employer_names_seen: int
    organizations_created: int
    opportunities_linked: int
    leads_linked: int
    contacts_linked: int
    dry_run: bool


def _collect_employer_names(session: Session) -> dict[str, str]:
    """Map normalized employer name -> preferred display label (first seen)."""
    labels: dict[str, str] = {}

    def add(raw: str | None) -> None:
        if raw is None:
            return
        label = raw.strip()
        if not label:
            return
        key = _normalize_employer(label)
        labels.setdefault(key, label)

    for employer in session.scalars(
        select(OpportunityProjectionDB.employer_name).distinct()
    ):
        add(employer)

    for employer in session.scalars(select(LeadDB.employer).distinct()):
        add(employer)

    for company in session.scalars(select(ContactDB.company).distinct()):
        add(company)

    return labels


def backfill_organizations_from_pipeline(
    session: Session,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> OrganizationBackfillResult:
    """Create missing org rows and link opportunities, leads, and contacts."""
    timestamp = now or datetime.now(timezone.utc)
    labels = _collect_employer_names(session)
    created = 0

    for label in labels.values():
        if find_organization_for_employer(session, label) is not None:
            continue
        if dry_run:
            created += 1
            continue
        org_id = f"organization-{uuid.uuid4()}"
        session.add(
            OrganizationDB(
                id=org_id,
                name=label,
                domain=None,
                industry=None,
                size=None,
                advocacy_rating=None,
                notes="Backfilled from pipeline employer data.",
                source_event_id="backfill-organizations",
                source_event_position="backfill-organizations",
                projected_at=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        created += 1

    if not dry_run and created:
        session.flush()

    opportunities_linked = 0
    for row in session.scalars(select(OpportunityProjectionDB)):
        org_id = resolve_link(session, row.employer_name, row.organization_id)
        if org_id is None or org_id == row.organization_id:
            continue
        opportunities_linked += 1
        if not dry_run:
            row.organization_id = org_id

    leads_linked = 0
    for row in session.scalars(select(LeadDB)):
        org_id = resolve_link(session, row.employer, row.organization_id)
        if org_id is None or org_id == row.organization_id:
            continue
        leads_linked += 1
        if not dry_run:
            row.organization_id = org_id

    contacts_linked = 0
    for row in session.scalars(select(ContactDB)):
        org_id = resolve_link(session, row.company, row.organization_id)
        if org_id is None or org_id == row.organization_id:
            continue
        contacts_linked += 1
        if not dry_run:
            row.organization_id = org_id

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return OrganizationBackfillResult(
        employer_names_seen=len(labels),
        organizations_created=created,
        opportunities_linked=opportunities_linked,
        leads_linked=leads_linked,
        contacts_linked=contacts_linked,
        dry_run=dry_run,
    )


def resolve_link(
    session: Session,
    employer_name: str | None,
    current_organization_id: str | None,
) -> str | None:
    if current_organization_id:
        return current_organization_id
    row = find_organization_for_employer(session, employer_name or "")
    return row.id if row is not None else None
