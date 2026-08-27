"""Tests for pipeline organization backfill."""

from datetime import datetime, timezone

from core.jobsearch_models import LeadDB, OpportunityProjectionDB, OrganizationDB
from core.jobsearch_organization_backfill import backfill_organizations_from_pipeline
from core.models import ContactDB


def _freshness(now: datetime) -> dict[str, datetime | str]:
    return {
        "source_event_id": "test",
        "source_event_position": "test",
        "projected_at": now,
        "created_at": now,
        "updated_at": now,
    }


def test_backfill_creates_orgs_and_links_opportunities(db_session):
    now = datetime.now(timezone.utc)
    freshness = _freshness(now)

    db_session.add(
        OpportunityProjectionDB(
            id="opportunity-1",
            employer_name="Deepgram",
            title="Solutions Architect",
            state="discovered",
            organization_id=None,
            risk_flags=[],
            evidence_refs=[],
            **freshness,
        )
    )
    db_session.add(
        OpportunityProjectionDB(
            id="opportunity-2",
            employer_name="deepgram",
            title="Staff Engineer",
            state="discovered",
            organization_id=None,
            risk_flags=[],
            evidence_refs=[],
            **freshness,
        )
    )
    db_session.add(
        LeadDB(
            id="lead-1",
            source_board="linkedin",
            employer="OpenAI",
            title="Director",
            organization_id=None,
            **freshness,
        )
    )
    db_session.add(
        ContactDB(
            id="contact-1",
            name="Alex",
            company="Parloa",
            organization_id=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    result = backfill_organizations_from_pipeline(db_session, now=now)

    assert result.organizations_created == 3
    assert result.opportunities_linked == 2
    assert result.leads_linked == 1
    assert result.contacts_linked == 1

    orgs = db_session.query(OrganizationDB).order_by(OrganizationDB.name).all()
    assert [org.name for org in orgs] == ["Deepgram", "OpenAI", "Parloa"]

    opp1 = db_session.get(OpportunityProjectionDB, "opportunity-1")
    opp2 = db_session.get(OpportunityProjectionDB, "opportunity-2")
    assert opp1.organization_id == opp2.organization_id

    lead = db_session.get(LeadDB, "lead-1")
    contact = db_session.get(ContactDB, "contact-1")
    assert lead.organization_id is not None
    assert contact.organization_id is not None


def test_backfill_is_idempotent(db_session):
    now = datetime.now(timezone.utc)
    freshness = _freshness(now)
    db_session.add(
        OrganizationDB(
            id="organization-existing",
            name="Deepgram",
            **freshness,
        )
    )
    db_session.add(
        OpportunityProjectionDB(
            id="opportunity-1",
            employer_name="Deepgram",
            title="Architect",
            state="discovered",
            organization_id=None,
            risk_flags=[],
            evidence_refs=[],
            **freshness,
        )
    )
    db_session.commit()

    result = backfill_organizations_from_pipeline(db_session, now=now)

    assert result.organizations_created == 0
    assert result.opportunities_linked == 1
    assert db_session.query(OrganizationDB).count() == 1
