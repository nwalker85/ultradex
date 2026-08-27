"""Tests for opportunity ↔ organization linking."""

from datetime import datetime, timezone

from core.jobsearch_models import (
    OpportunityProjectionDB,
    OrganizationDB,
    ProjectionCheckpointDB,
)
from core.jobsearch_organization_resolve import resolve_organization_id


def test_resolve_organization_id_by_name(db_session):
    org = OrganizationDB(
        id="organization-acme",
        name="Acme Corp",
        source_event_id="test",
        source_event_position="0",
        projected_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(org)
    db_session.commit()

    assert (
        resolve_organization_id(db_session, "acme corp")
        == "organization-acme"
    )


def test_list_opportunities_filters_by_organization(db_session):
    from core.jobsearch_projections import JobSearchProjectionRepository

    org = OrganizationDB(
        id="organization-filter",
        name="FilterCo",
        source_event_id="test",
        source_event_position="0",
        projected_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    now = datetime.now(timezone.utc)
    linked = OpportunityProjectionDB(
        id="opportunity-linked",
        organization_id="organization-filter",
        employer_name="FilterCo",
        title="Staff Engineer",
        state="discovered",
        risk_flags=[],
        evidence_refs=[],
        source_event_id="test",
        source_event_position="0",
        projected_at=now,
        created_at=now,
        updated_at=now,
    )
    other = OpportunityProjectionDB(
        id="opportunity-other",
        organization_id=None,
        employer_name="OtherCo",
        title="PM",
        state="discovered",
        risk_flags=[],
        evidence_refs=[],
        source_event_id="test",
        source_event_position="0",
        projected_at=now,
        created_at=now,
        updated_at=now,
    )
    checkpoint = ProjectionCheckpointDB(
        projection_type="opportunities",
        source_event_id="test",
        source_event_position="0",
        projected_at=now,
        lag_ms=0,
        status="fresh",
    )
    db_session.add_all([org, linked, other, checkpoint])
    db_session.commit()

    page = JobSearchProjectionRepository(db_session).list_opportunities(
        first=10,
        organization_id="organization-filter",
    )
    ids = {item.opportunity_id for item in page.items}
    assert ids == {"opportunity-linked"}
