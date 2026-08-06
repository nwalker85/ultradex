from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest
from ravenhelm_contracts import (
    ApplicationV1,
    OpportunityV1,
    OutreachV1,
    ProjectionFreshnessV1,
    RelationshipV1,
)
from ravenhelm_contracts.jobsearch_v1 import JOBSEARCH_PROJECTION_TYPES_V1
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from core import (
    JOBSEARCH_PROJECTION_TYPES,
    JobSearchProjectionRepository,
    ProjectedOutreach,
    ProjectionPage,
)
from core.jobsearch_models import (
    ApplicationProjectionDB,
    JobSearchApprovalDB,
    JobSearchExecutionReceiptDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)
from core.models import Base


NOW = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)
VALID_COMMITMENT = f"sha256:{'a' * 64}"
VALID_RECEIPT_HASH = (
    "sha256:e18c64598f2b5ed18116c8a00403bba04bb3f219d222377880a66fa56683d145"
)
VALID_RECEIPT_PAYLOAD: dict[str, object] = {
    "contract_version": "accountability.v1",
    "receipt_id": "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
    "event_id": "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
    "stream_pairwise_id": "pairwise:v1:SSSSSSSSSSSSSSSSSSSSSS",
    "sequence": 1,
    "subject_pairwise_id": "pairwise:v1:UUUUUUUUUUUUUUUUUUUUUU",
    "tenant_scope": {
        "scheme": "hmac_sha256_v1",
        "purpose": "jobsearch_operation",
        "digest": (
            "sha256:"
            "1111111111111111111111111111111111111111111111111111111111111111"
        ),
    },
    "purpose": "jobsearch_operation",
    "request_id": "opaque:v1:QQQQQQQQQQQQQQQQQQQQQQ",
    "idempotency_key": "opaque:v1:IIIIIIIIIIIIIIIIIIIIII",
    "action_commitment": {
        "scheme": "hmac_sha256_v1",
        "purpose": "jobsearch_operation",
        "digest": (
            "sha256:"
            "2222222222222222222222222222222222222222222222222222222222222222"
        ),
    },
    "execution_id": "opaque:v1:XXXXXXXXXXXXXXXXXXXXXX",
    "executor_pairwise_id": "pairwise:v1:ZZZZZZZZZZZZZZZZZZZZZZ",
    "status": "succeeded",
    "started_at": "2026-07-23T06:00:00.000Z",
    "completed_at": "2026-07-23T06:01:00.000Z",
    "result_commitment": {
        "scheme": "hmac_sha256_v1",
        "purpose": "jobsearch_operation",
        "digest": (
            "sha256:"
            "3333333333333333333333333333333333333333333333333333333333333333"
        ),
    },
    "reason_code": None,
    "daml_transaction": None,
    "signature": {
        "algorithm": "ed25519",
        "key_id": "pairwise:v1:KKKKKKKKKKKKKKKKKKKKKK",
        "signature": (
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
    },
}


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
            _freshness("opportunities"),
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
            _freshness("opportunities"),
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


def test_repository_projection_types_match_canonical_contract():
    assert JOBSEARCH_PROJECTION_TYPES == JOBSEARCH_PROJECTION_TYPES_V1


@pytest.mark.parametrize(
    ("row", "projection_type", "method_name"),
    [
        (
            _opportunity("opportunity-01"),
            "opportunities",
            "list_opportunities",
        ),
        (
            _application("application-01"),
            "applications",
            "list_applications",
        ),
        (
            _relationship("relationship-01"),
            "relationships",
            "list_relationships",
        ),
        (
            _outreach("outreach-01"),
            "outreach",
            "list_outreach",
        ),
    ],
)
def test_every_page_uses_its_canonical_checkpoint_key(
    db_session: Session,
    row: object,
    projection_type: str,
    method_name: str,
) -> None:
    checkpoint = _freshness(projection_type)
    checkpoint.source_event_id = f"checkpoint-{projection_type}"
    db_session.add_all([row, checkpoint])
    db_session.commit()

    page = getattr(JobSearchProjectionRepository(db_session), method_name)(
        first=10,
        after=None,
    )

    assert page.freshness is not None
    assert page.freshness.source_event_id == f"checkpoint-{projection_type}"


@pytest.mark.parametrize(
    ("row", "checkpoint_type", "method_name", "expected_id"),
    [
        (
            _application("application-01", opportunity_id="opportunity-match"),
            "applications",
            "list_applications",
            "application-01",
        ),
        (
            _relationship("relationship-01", opportunity_id="opportunity-match"),
            "relationships",
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
    page_item = page.items[0]
    if isinstance(page_item, ProjectedOutreach):
        page_item = page_item.item
    item_id = getattr(page_item, id_field)
    assert item_id == expected_id
    assert "opportunity_id" in statements[0].lower()
    assert "where" in statements[0].lower()


@pytest.mark.parametrize(
    ("row", "checkpoint_type", "method_name", "status"),
    [
        (
            _opportunity("opportunity-01", state="qualified"),
            "opportunities",
            "list_opportunities",
            "qualified",
        ),
        (
            _application("application-01", state="applied"),
            "applications",
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
        [_opportunity("opportunity-01"), _freshness("opportunities")]
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
            "opportunities",
            "list_opportunities",
        ),
        (
            _opportunity(
                "opportunity-01",
                evidence_refs=[_evidence(raw_content="secret")],
            ),
            "opportunities",
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
            "opportunities",
            "list_opportunities",
        ),
        (
            _relationship(
                "relationship-01",
                relevance_reason="x" * 501,
            ),
            "relationships",
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


def test_outreach_detail_and_list_share_validated_row_provenance(
    db_session: Session,
) -> None:
    row = _outreach("outreach-01")
    row.projected_at = NOW
    checkpoint = _freshness("outreach")
    checkpoint.projected_at = NOW + timedelta(minutes=5)
    db_session.add_all([row, checkpoint])
    db_session.commit()
    repository = JobSearchProjectionRepository(db_session)

    detail = repository.get_outreach("outreach-01")
    page = repository.list_outreach(first=10)

    assert isinstance(detail, ProjectedOutreach)
    assert isinstance(detail.item, OutreachV1)
    assert isinstance(detail.freshness, ProjectionFreshnessV1)
    assert page.items == (detail,)
    assert detail.freshness.source_event_id == "event-row"
    assert detail.freshness.source_event_position == "JOBSEARCH:41"
    assert detail.freshness.projected_at == "2026-07-23T06:00:00Z"
    assert detail.freshness.lag_ms == 125
    assert detail.freshness.status == "stale"
    assert page.freshness is not None
    assert page.freshness.source_event_id == "event-42"
    assert page.freshness.projected_at == "2026-07-23T06:05:00Z"
    with pytest.raises(FrozenInstanceError):
        detail.item = detail.item


@pytest.mark.parametrize("method_name", ["get_outreach", "list_outreach"])
def test_outreach_with_missing_checkpoint_fails_closed(
    db_session: Session,
    method_name: str,
) -> None:
    db_session.add(_outreach("outreach-01"))
    db_session.commit()
    method = getattr(JobSearchProjectionRepository(db_session), method_name)

    with pytest.raises(ValueError, match="no projection checkpoint"):
        if method_name == "get_outreach":
            method("outreach-01")
        else:
            method(first=10)


def test_detail_methods_return_contracts_and_none_for_unknown_ids(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            _opportunity("opportunity-01"),
            _application("application-01"),
            _relationship("relationship-01"),
            _outreach("outreach-01"),
            _freshness("opportunities"),
            _freshness("applications"),
            _freshness("relationships"),
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
    outreach = repository.get_outreach("outreach-01")
    assert isinstance(outreach, ProjectedOutreach)
    assert isinstance(outreach.item, OutreachV1)
    assert repository.get_opportunity("missing") is None
    assert repository.get_application("missing") is None
    assert repository.get_relationship("missing") is None
    assert repository.get_outreach("missing") is None


def test_get_approval_resolves_exact_primary_id_with_complete_binding(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            JobSearchApprovalDB(
                approval_id="approval-01",
                outreach_id="outreach-01",
                message_commitment=f"sha256:{'4' * 64}",
                channel="gmail",
                approved_by="operator:synthetic-one",
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=24),
                status="approved",
            ),
            JobSearchApprovalDB(
                approval_id="approval-02",
                outreach_id="outreach-02",
                message_commitment=f"sha256:{'5' * 64}",
                channel="linkedin",
                approved_by="operator:synthetic-two",
                issued_at=NOW + timedelta(minutes=1),
                expires_at=NOW + timedelta(hours=12),
                status="approved",
            ),
        ]
    )
    db_session.commit()

    repository = JobSearchProjectionRepository(db_session)
    approval = repository.get_approval("approval-02")

    assert approval is not None
    assert approval.approval_id == "approval-02"
    assert approval.outreach_id == "outreach-02"
    assert approval.message_commitment == f"sha256:{'5' * 64}"
    assert approval.channel == "linkedin"
    assert approval.approved_by == "operator:synthetic-two"
    assert approval.issued_at == "2026-07-23T06:01:00Z"
    assert approval.expires_at == "2026-07-23T18:00:00Z"
    assert approval.status == "approved"
    assert repository.get_approval("approval-missing") is None


def test_get_execution_receipt_resolves_unique_operation_and_decodes_contract(
    db_session: Session,
) -> None:
    db_session.add(
        JobSearchExecutionReceiptDB(
            receipt_id="opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
            operation_id="operation-synthetic-01",
            event_id="opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
            status="succeeded",
            reason_code=None,
            payload=VALID_RECEIPT_PAYLOAD,
            receipt_hash=VALID_RECEIPT_HASH,
            created_at=NOW,
            completed_at=NOW
            + timedelta(minutes=1, seconds=47, microseconds=999_999),
        )
    )
    db_session.commit()

    repository = JobSearchProjectionRepository(db_session)
    evidence = repository.get_execution_receipt("operation-synthetic-01")

    assert evidence is not None
    assert evidence.operation_id == "operation-synthetic-01"
    assert evidence.receipt.receipt_id == "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR"
    assert evidence.receipt.event_id == "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE"
    assert evidence.receipt.status == "succeeded"
    assert evidence.receipt.reason_code is None
    assert (
        evidence.receipt.signature.key_id
        == "pairwise:v1:KKKKKKKKKKKKKKKKKKKKKK"
    )
    assert evidence.receipt_hash == VALID_RECEIPT_HASH
    assert evidence.created_at == "2026-07-23T06:00:00Z"
    assert evidence.completed_at == "2026-07-23T06:01:00Z"
    assert evidence.proof_status == "server-recorded"
    assert repository.get_execution_receipt("operation-missing") is None


def test_get_execution_receipt_rejects_row_completion_from_different_signed_minute(
    db_session: Session,
) -> None:
    row = JobSearchExecutionReceiptDB(
        receipt_id="opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
        operation_id="operation-synthetic-01",
        event_id="opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
        status="succeeded",
        reason_code=None,
        payload=VALID_RECEIPT_PAYLOAD,
        receipt_hash=VALID_RECEIPT_HASH,
        created_at=NOW,
        completed_at=NOW + timedelta(minutes=1, seconds=30),
    )
    db_session.add(row)
    db_session.commit()

    row.completed_at = NOW + timedelta(minutes=2)
    db_session.commit()

    repository = JobSearchProjectionRepository(db_session)
    with pytest.raises(
        ValueError,
        match="completed_at does not match signed payload",
    ):
        repository.get_execution_receipt(row.operation_id)


@pytest.mark.parametrize(
    "row",
    [
        JobSearchApprovalDB(
            approval_id="approval-invalid",
            outreach_id="outreach-01",
            message_commitment="not-a-commitment",
            channel="gmail",
            approved_by="operator:synthetic",
            issued_at=NOW,
            expires_at=NOW + timedelta(hours=24),
            status="approved",
        ),
        JobSearchExecutionReceiptDB(
            receipt_id="opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
            operation_id="operation-invalid",
            event_id="opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
            status="succeeded",
            reason_code=None,
            payload={
                key: value
                for key, value in VALID_RECEIPT_PAYLOAD.items()
                if key != "signature"
            },
            receipt_hash=VALID_RECEIPT_HASH,
            created_at=NOW,
            completed_at=NOW + timedelta(minutes=1),
        ),
    ],
)
def test_governed_evidence_reads_reject_malformed_rows(
    db_session: Session,
    row: object,
) -> None:
    db_session.add(row)
    db_session.commit()
    repository = JobSearchProjectionRepository(db_session)

    with pytest.raises(ValueError):
        if isinstance(row, JobSearchApprovalDB):
            repository.get_approval(row.approval_id)
        else:
            repository.get_execution_receipt(row.operation_id)
