from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import pytest
from ravenhelm_contracts import (
    ApplicationV1,
    OpportunityV1,
    OutreachV1,
    RelationshipV1,
)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from core import JobSearchProjectionRepository, ProjectionPage
from core.jobsearch_models import (
    ApplicationProjectionDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)
from core.models import Base


NOW = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)
VALID_COMMITMENT = f"sha256:{'a' * 64}"


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _freshness(projection_type: str) -> ProjectionCheckpointDB:
    return ProjectionCheckpointDB(
        projection_type=projection_type,
        source_event_id="event-42",
        source_event_position="JOBSEARCH:42",
        projected_at=NOW,
        lag_ms=125,
        status="stale",
    )


def _evidence(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": "evidence-01",
        "source_kind": "manual",
        "source_ref": "manual-source-01",
        "classification": "private",
        "observed_at": "2026-07-23T06:00:00Z",
        "commitment": VALID_COMMITMENT,
        "redacted_summary": "Public job description reviewed.",
    }
    payload.update(overrides)
    return payload


def _opportunity(
    opportunity_id: str,
    *,
    state: str = "qualified",
    evidence_refs: list[dict[str, object]] | None = None,
    score_explanation: str | None = "Strong platform fit.",
) -> OpportunityProjectionDB:
    return OpportunityProjectionDB(
        id=opportunity_id,
        employer_name="Example Corp",
        title="Platform Engineer",
        location="Remote",
        role_family="Engineering",
        state=state,
        score=91,
        score_explanation=score_explanation,
        risk_flags=["compensation-unverified"],
        evidence_refs=[_evidence()] if evidence_refs is None else evidence_refs,
        source_event_id="event-row",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _application(
    application_id: str,
    *,
    opportunity_id: str = "opportunity-01",
    state: str = "applied",
) -> ApplicationProjectionDB:
    return ApplicationProjectionDB(
        id=application_id,
        opportunity_id=opportunity_id,
        state=state,
        stage_history=[
            {
                "status": state,
                "occurred_at": "2026-07-23T06:00:00Z",
                "evidence_ref": "evidence-01",
            }
        ],
        artifact_refs=["artifact-resume-01"],
        next_action="Follow up",
        next_action_deadline=NOW,
        source_event_id="event-row",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _relationship(
    relationship_id: str,
    *,
    opportunity_id: str = "opportunity-01",
    relevance_reason: str | None = "Former colleague at the employer.",
) -> RelationshipProjectionDB:
    return RelationshipProjectionDB(
        id=relationship_id,
        opportunity_id=opportunity_id,
        dex_contact_ref="dex-contact-01",
        relevance_score=88,
        relevance_reason=relevance_reason,
        relevance_signals=["former-colleague"],
        source_event_id="event-row",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _outreach(
    outreach_id: str,
    *,
    opportunity_id: str = "opportunity-01",
    state: str = "draft",
    message_commitment: str = VALID_COMMITMENT,
) -> OutreachProjectionDB:
    return OutreachProjectionDB(
        id=outreach_id,
        opportunity_id=opportunity_id,
        relationship_id="relationship-01",
        state=state,
        channel="gmail",
        message_commitment=message_commitment,
        approval_contract_ref="contract-01",
        sent_evidence_ref="evidence-01",
        source_event_id="event-row",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def test_list_opportunities_returns_bounded_contract_page(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            _opportunity("opportunity-03"),
            _opportunity("opportunity-01"),
            _opportunity("opportunity-02"),
            _opportunity("opportunity-00", state="archived"),
            _freshness("opportunity"),
        ]
    )
    db_session.commit()

    page = JobSearchProjectionRepository(db_session).list_opportunities(
        first=2,
        after=None,
        status="qualified",
    )

    assert isinstance(page, ProjectionPage)
    assert isinstance(page.items, tuple)
    assert all(isinstance(item, OpportunityV1) for item in page.items)
    assert [item.opportunity_id for item in page.items] == [
        "opportunity-01",
        "opportunity-02",
    ]
    assert page.next_cursor == "opportunity-02"
    assert page.freshness is not None
    assert page.freshness.source_event_position == "JOBSEARCH:42"
    assert page.freshness.lag_ms == 125
    assert page.freshness.status == "stale"
    assert page.items[0].freshness.source_event_id == "event-row"
    assert page.items[0].freshness.source_event_position == "JOBSEARCH:41"
    assert page.items[0].freshness.lag_ms == page.freshness.lag_ms
    assert page.items[0].freshness.status == page.freshness.status
    assert page.items[0].created_at.endswith("Z")
    assert page.items[0].freshness.projected_at.endswith("Z")
    assert page.freshness.projected_at.endswith("Z")


@pytest.mark.parametrize("first", [0, 101])
def test_list_rejects_out_of_bounds_first(
    db_session: Session,
    first: int,
) -> None:
    with pytest.raises(ValueError, match="first"):
        JobSearchProjectionRepository(db_session).list_opportunities(
            first=first,
            after=None,
            status=None,
        )


def test_after_uses_stable_primary_key_cursor(db_session: Session) -> None:
    db_session.add_all(
        [
            _opportunity("opportunity-01"),
            _opportunity("opportunity-02"),
            _opportunity("opportunity-03"),
            _freshness("opportunity"),
        ]
    )
    db_session.commit()

    page = JobSearchProjectionRepository(db_session).list_opportunities(
        first=2,
        after="opportunity-01",
        status=None,
    )

    assert [item.opportunity_id for item in page.items] == [
        "opportunity-02",
        "opportunity-03",
    ]
    assert page.next_cursor is None


@pytest.mark.parametrize(
    ("method_name", "status"),
    [
        ("list_opportunities", "not-an-opportunity-status"),
        ("list_applications", "not-an-application-status"),
        ("list_outreach", "not-an-outreach-status"),
    ],
)
def test_list_rejects_noncanonical_status_filters(
    db_session: Session,
    method_name: str,
    status: str,
) -> None:
    repository = JobSearchProjectionRepository(db_session)
    method = getattr(repository, method_name)

    with pytest.raises(ValueError, match="status"):
        method(first=10, after=None, status=status)


@pytest.mark.parametrize(
    ("row", "checkpoint_type", "method_name", "expected_id"),
    [
        (
            _application("application-01", opportunity_id="opportunity-match"),
            "application",
            "list_applications",
            "application-01",
        ),
        (
            _relationship("relationship-01", opportunity_id="opportunity-match"),
            "relationship",
            "list_relationships",
            "relationship-01",
        ),
        (
            _outreach("outreach-01", opportunity_id="opportunity-match"),
            "outreach",
            "list_outreach",
            "outreach-01",
        ),
    ],
)
def test_opportunity_filters_are_applied_in_sql(
    db_session: Session,
    row: object,
    checkpoint_type: str,
    method_name: str,
    expected_id: str,
) -> None:
    db_session.add_all([row, _freshness(checkpoint_type)])
    db_session.commit()
    statements: list[str] = []
    event.listen(
        db_session.bind,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _parameters, _context, _many: (
            statements.append(statement)
        ),
    )

    repository = JobSearchProjectionRepository(db_session)
    method = getattr(repository, method_name)
    page = method(
        first=10,
        after=None,
        opportunity_id="opportunity-match",
    )

    id_field = {
        "list_applications": "application_id",
        "list_relationships": "relationship_id",
        "list_outreach": "outreach_id",
    }[method_name]
    item_id = getattr(page.items[0], id_field)
    assert item_id == expected_id
    assert "opportunity_id" in statements[0].lower()
    assert "where" in statements[0].lower()


@pytest.mark.parametrize(
    ("row", "checkpoint_type", "method_name", "status"),
    [
        (
            _opportunity("opportunity-01", state="qualified"),
            "opportunity",
            "list_opportunities",
            "qualified",
        ),
        (
            _application("application-01", state="applied"),
            "application",
            "list_applications",
            "applied",
        ),
        (
            _outreach("outreach-01", state="approved"),
            "outreach",
            "list_outreach",
            "approved",
        ),
    ],
)
def test_status_filters_are_applied_in_sql(
    db_session: Session,
    row: object,
    checkpoint_type: str,
    method_name: str,
    status: str,
) -> None:
    db_session.add_all([row, _freshness(checkpoint_type)])
    db_session.commit()
    statements: list[str] = []
    event.listen(
        db_session.bind,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _parameters, _context, _many: (
            statements.append(statement)
        ),
    )

    repository = JobSearchProjectionRepository(db_session)
    method = getattr(repository, method_name)
    page = method(first=10, after=None, status=status)

    assert len(page.items) == 1
    assert "state" in statements[0].lower()
    assert "where" in statements[0].lower()


def test_list_without_checkpoint_reports_unknown_freshness(
    db_session: Session,
) -> None:
    page = JobSearchProjectionRepository(db_session).list_opportunities(
        first=10,
        after=None,
        status=None,
    )

    assert page.items == ()
    assert page.freshness is None


def test_list_executes_at_most_page_and_checkpoint_queries(
    db_session: Session,
) -> None:
    db_session.add_all(
        [_opportunity("opportunity-01"), _freshness("opportunity")]
    )
    db_session.commit()
    statements: list[str] = []
    event.listen(
        db_session.bind,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _parameters, _context, _many: (
            statements.append(statement)
        ),
    )

    JobSearchProjectionRepository(db_session).list_opportunities(
        first=10,
        after=None,
        status=None,
    )

    assert len(statements) <= 2


@pytest.mark.parametrize(
    ("row", "checkpoint_type", "method_name"),
    [
        (
            _opportunity(
                "opportunity-01",
                evidence_refs=[{"evidence_id": "evidence-01"}],
            ),
            "opportunity",
            "list_opportunities",
        ),
        (
            _opportunity(
                "opportunity-01",
                evidence_refs=[_evidence(raw_content="secret")],
            ),
            "opportunity",
            "list_opportunities",
        ),
        (
            _outreach(
                "outreach-01",
                message_commitment="not-a-sha256-commitment",
            ),
            "outreach",
            "list_outreach",
        ),
        (
            _opportunity("opportunity-01", state="not-a-status"),
            "opportunity",
            "list_opportunities",
        ),
        (
            _relationship(
                "relationship-01",
                relevance_reason="x" * 501,
            ),
            "relationship",
            "list_relationships",
        ),
    ],
)
def test_rows_must_pass_canonical_contract_validation(
    db_session: Session,
    row: object,
    checkpoint_type: str,
    method_name: str,
) -> None:
    db_session.add_all([row, _freshness(checkpoint_type)])
    db_session.commit()
    repository = JobSearchProjectionRepository(db_session)
    method: Callable[..., object] = getattr(repository, method_name)

    with pytest.raises(ValueError):
        method(first=10, after=None)


def test_detail_methods_return_contracts_and_none_for_unknown_ids(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            _opportunity("opportunity-01"),
            _application("application-01"),
            _relationship("relationship-01"),
            _outreach("outreach-01"),
            _freshness("opportunity"),
            _freshness("application"),
            _freshness("relationship"),
            _freshness("outreach"),
        ]
    )
    db_session.commit()
    repository = JobSearchProjectionRepository(db_session)

    assert isinstance(
        repository.get_opportunity("opportunity-01"),
        OpportunityV1,
    )
    assert isinstance(
        repository.get_application("application-01"),
        ApplicationV1,
    )
    assert isinstance(
        repository.get_relationship("relationship-01"),
        RelationshipV1,
    )
    assert isinstance(repository.get_outreach("outreach-01"), OutreachV1)
    assert repository.get_opportunity("missing") is None
    assert repository.get_application("missing") is None
    assert repository.get_relationship("missing") is None
    assert repository.get_outreach("missing") is None
