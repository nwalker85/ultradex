from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import event

from api.graphql.schema import schema
from api.main import app
from core import get_db
from core.jobsearch_models import (
    ApplicationProjectionDB,
    JobSearchApprovalDB,
    JobSearchExecutionReceiptDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)


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


def _checkpoint(projection_type: str) -> ProjectionCheckpointDB:
    return ProjectionCheckpointDB(
        projection_type=projection_type,
        source_event_id=f"event-checkpoint-{projection_type}",
        source_event_position="JOBSEARCH:42",
        projected_at=NOW,
        lag_ms=125,
        status="stale",
    )


def _opportunity(
    opportunity_id: str,
    *,
    employer: str = "Example Corp",
    status: str = "qualified",
) -> OpportunityProjectionDB:
    return OpportunityProjectionDB(
        id=opportunity_id,
        employer_name=employer,
        title="Platform Engineer",
        location="Remote",
        role_family="Engineering",
        state=status,
        score=91,
        score_explanation="Strong platform fit.",
        risk_flags=["compensation-unverified"],
        evidence_refs=[
            {
                "evidence_id": f"evidence-{opportunity_id}",
                "source_kind": "manual",
                "source_ref": f"manual-{opportunity_id}",
                "classification": "private",
                "observed_at": "2026-07-23T06:00:00Z",
                "commitment": VALID_COMMITMENT,
                "redacted_summary": "Public job description reviewed.",
            }
        ],
        source_event_id=f"event-{opportunity_id}",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _application(application_id: str) -> ApplicationProjectionDB:
    return ApplicationProjectionDB(
        id=application_id,
        opportunity_id="opportunity-01",
        state="applied",
        stage_history=[
            {
                "status": "draft",
                "occurred_at": "2026-07-23T05:00:00Z",
                "evidence_ref": "evidence-draft-01",
            },
            {
                "status": "applied",
                "occurred_at": "2026-07-23T06:00:00Z",
                "evidence_ref": "evidence-applied-01",
            },
        ],
        artifact_refs=["artifact-resume-01", "artifact-cover-letter-01"],
        next_action="Follow up",
        next_action_deadline=NOW,
        source_event_id=f"event-{application_id}",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _relationship(relationship_id: str) -> RelationshipProjectionDB:
    return RelationshipProjectionDB(
        id=relationship_id,
        opportunity_id="opportunity-01",
        dex_contact_ref="dex-contact-01",
        relevance_score=88,
        relevance_reason="Former colleague at the employer.",
        source_event_id=f"event-{relationship_id}",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _outreach(outreach_id: str) -> OutreachProjectionDB:
    return OutreachProjectionDB(
        id=outreach_id,
        opportunity_id="opportunity-01",
        relationship_id="relationship-01",
        state="pending_approval",
        channel="gmail",
        message_commitment=VALID_COMMITMENT,
        approval_contract_ref="contract-01",
        sent_evidence_ref=None,
        source_event_id=f"event-{outreach_id}",
        source_event_position="JOBSEARCH:41",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _approval(approval_id: str, outreach_id: str) -> JobSearchApprovalDB:
    return JobSearchApprovalDB(
        approval_id=approval_id,
        outreach_id=outreach_id,
        message_commitment=VALID_COMMITMENT,
        channel="gmail",
        approved_by="operator:synthetic",
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=24),
        status="approved",
    )


def _receipt(operation_id: str) -> JobSearchExecutionReceiptDB:
    return JobSearchExecutionReceiptDB(
        receipt_id="opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
        operation_id=operation_id,
        event_id="opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
        status="succeeded",
        reason_code=None,
        payload=VALID_RECEIPT_PAYLOAD,
        receipt_hash=VALID_RECEIPT_HASH,
        created_at=NOW,
        completed_at=NOW + timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_opportunities_are_bounded_canonical_and_do_not_query_per_item(
    db_session,
):
    db_session.add_all(
        [
            _opportunity("opportunity-03", employer="Third Corp"),
            _opportunity("opportunity-01", employer="First Corp"),
            _opportunity("opportunity-02", employer="Second Corp"),
            _opportunity(
                "opportunity-00",
                employer="Archived Corp",
                status="archived",
            ),
            _checkpoint("opportunities"),
        ]
    )
    db_session.commit()
    detail_result = await schema.execute(
        """
        query {
          opportunity(id: "opportunity-01") {
            opportunityId
            employer
          }
        }
        """,
        context_value={"db": db_session},
    )
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        result = await schema.execute(
            """
            query {
              opportunities(first: 2, status: "qualified") {
                items {
                  opportunityId
                  employer
                  evidenceRefs {
                    sourceKind
                    sourceRef
                    commitment
                    redactedSummary
                  }
                  freshness {
                    sourceEventId
                    sourceEventPosition
                    projectedAt
                    lagMs
                    status
                  }
                }
                freshness { sourceEventPosition status }
                nextCursor
              }
            }
            """,
            context_value={"db": db_session},
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)

    assert detail_result.errors is None
    assert result.errors is None
    assert detail_result.data["opportunity"] == {
        "opportunityId": "opportunity-01",
        "employer": "First Corp",
    }
    page = result.data["opportunities"]
    assert [item["opportunityId"] for item in page["items"]] == [
        "opportunity-01",
        "opportunity-02",
    ]
    assert page["items"][0]["employer"] == (
        detail_result.data["opportunity"]["employer"]
    )
    assert page["items"][0]["evidenceRefs"] == [
        {
            "sourceKind": "manual",
            "sourceRef": "manual-opportunity-01",
            "commitment": VALID_COMMITMENT,
            "redactedSummary": "Public job description reviewed.",
        }
    ]
    assert page["items"][0]["freshness"]["sourceEventId"] == (
        "event-opportunity-01"
    )
    assert page["items"][0]["freshness"]["sourceEventPosition"] == "JOBSEARCH:41"
    assert page["items"][0]["freshness"]["lagMs"] == 125
    assert page["items"][0]["freshness"]["status"] == "stale"
    assert page["items"][0]["freshness"]["projectedAt"].startswith(
        "2026-07-23T06:00:00"
    )
    assert page["freshness"] == {
        "sourceEventPosition": "JOBSEARCH:42",
        "status": "stale",
    }
    assert page["nextCursor"] == "opportunity-02"

    opportunity_reads = [
        statement
        for statement in statements
        if "jobsearch_opportunities" in statement.lower()
    ]
    checkpoint_reads = [
        statement
        for statement in statements
        if "jobsearch_projection_checkpoints" in statement.lower()
    ]
    assert len(opportunity_reads) == 1
    assert len(checkpoint_reads) == 1


@pytest.mark.asyncio
async def test_application_detail_and_list_preserve_stage_and_artifact_order(
    db_session,
):
    db_session.add_all(
        [
            _application("application-01"),
            _checkpoint("applications"),
        ]
    )
    db_session.commit()

    result = await schema.execute(
        """
        query {
          application(id: "application-01") {
            applicationId
            opportunityId
            status
            stageHistory { status occurredAt evidenceRef }
            artifactRefs
          }
          applications(opportunityId: "opportunity-01") {
            items {
              applicationId
              stageHistory { status occurredAt evidenceRef }
              artifactRefs
            }
            freshness { sourceEventPosition status }
            nextCursor
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    detail = result.data["application"]
    listed = result.data["applications"]["items"]
    assert [item["applicationId"] for item in listed] == ["application-01"]
    assert listed[0]["stageHistory"] == detail["stageHistory"]
    assert detail["stageHistory"] == [
        {
            "status": "draft",
            "occurredAt": "2026-07-23T05:00:00+00:00",
            "evidenceRef": "evidence-draft-01",
        },
        {
            "status": "applied",
            "occurredAt": "2026-07-23T06:00:00+00:00",
            "evidenceRef": "evidence-applied-01",
        },
    ]
    assert detail["artifactRefs"] == [
        "artifact-resume-01",
        "artifact-cover-letter-01",
    ]
    assert listed[0]["artifactRefs"] == detail["artifactRefs"]


@pytest.mark.asyncio
async def test_relationship_and_outreach_expose_only_privacy_safe_fields(
    db_session,
):
    db_session.add_all(
        [
            _relationship("relationship-01"),
            _outreach("outreach-01"),
            _checkpoint("relationships"),
            _checkpoint("outreach"),
        ]
    )
    db_session.commit()

    result = await schema.execute(
        """
        query {
          relationship(id: "relationship-01") {
            relationshipId
            opportunityId
            dexContactRef
            relevanceScore
            relevanceSummary
          }
          relationships(opportunityId: "opportunity-01") {
            items {
              relationshipId
              dexContactRef
              relevanceScore
              relevanceSummary
            }
          }
          outreachItem(id: "outreach-01") {
            outreachId
            messageCommitment
            freshness {
              sourceEventId
              sourceEventPosition
              projectedAt
              lagMs
              status
            }
          }
          outreach(status: "pending_approval", opportunityId: "opportunity-01") {
            items {
              outreachId
              messageCommitment
              freshness {
                sourceEventId
                sourceEventPosition
                projectedAt
                lagMs
                status
              }
            }
            freshness { sourceEventPosition status }
          }
          relationshipType: __type(name: "Relationship") {
            fields { name }
          }
          outreachType: __type(name: "Outreach") {
            fields {
              name
              type {
                kind
                ofType { kind name }
              }
            }
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    relationship = result.data["relationship"]
    assert relationship == {
        "relationshipId": "relationship-01",
        "opportunityId": "opportunity-01",
        "dexContactRef": "dex-contact-01",
        "relevanceScore": 88,
        "relevanceSummary": "Former colleague at the employer.",
    }
    assert result.data["relationships"]["items"][0] == {
        key: relationship[key]
        for key in (
            "relationshipId",
            "dexContactRef",
            "relevanceScore",
            "relevanceSummary",
        )
    }
    assert result.data["outreachItem"] == {
        "outreachId": "outreach-01",
        "messageCommitment": VALID_COMMITMENT,
        "freshness": {
            "sourceEventId": "event-outreach-01",
            "sourceEventPosition": "JOBSEARCH:41",
            "projectedAt": "2026-07-23T06:00:00+00:00",
            "lagMs": 125,
            "status": "stale",
        },
    }
    assert result.data["outreach"]["items"] == [result.data["outreachItem"]]

    relationship_fields = {
        field["name"] for field in result.data["relationshipType"]["fields"]
    }
    assert relationship_fields == {
        "relationshipId",
        "opportunityId",
        "dexContactRef",
        "relevanceScore",
        "relevanceSummary",
        "freshness",
        "createdAt",
        "updatedAt",
    }
    outreach_fields = {
        field["name"] for field in result.data["outreachType"]["fields"]
    }
    assert outreach_fields == {
        "outreachId",
        "opportunityId",
        "relationshipId",
        "status",
        "channel",
        "messageCommitment",
        "approvalContractId",
        "sentEvidenceRef",
        "freshness",
        "createdAt",
        "updatedAt",
    }
    outreach_field_types = {
        field["name"]: field["type"]
        for field in result.data["outreachType"]["fields"]
    }
    assert outreach_field_types["freshness"] == {
        "kind": "NON_NULL",
        "ofType": {"kind": "OBJECT", "name": "ProjectionFreshness"},
    }
    assert outreach_fields.isdisjoint(
        {"body", "subject", "prompt", "completion", "note", "draftText"}
    )


@pytest.mark.asyncio
async def test_empty_unprojected_pages_have_unknown_freshness(db_session):
    result = await schema.execute(
        """
        query {
          opportunities { items { opportunityId } freshness { status } nextCursor }
          applications { items { applicationId } freshness { status } nextCursor }
          relationships { items { relationshipId } freshness { status } nextCursor }
          outreach { items { outreachId } freshness { status } nextCursor }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    assert result.data == {
        "opportunities": {"items": [], "freshness": None, "nextCursor": None},
        "applications": {"items": [], "freshness": None, "nextCursor": None},
        "relationships": {"items": [], "freshness": None, "nextCursor": None},
        "outreach": {"items": [], "freshness": None, "nextCursor": None},
    }


@pytest.mark.asyncio
async def test_governed_evidence_reads_resolve_exact_bindings_and_recorded_receipt(
    db_session,
):
    db_session.add_all(
        [
            _approval("approval-01", "outreach-01"),
            _approval("approval-02", "outreach-02"),
            _receipt("operation-synthetic-01"),
        ]
    )
    db_session.commit()

    result = await schema.execute(
        """
        query GovernedEvidence($approvalId: String!, $operationId: String!) {
          approval(id: $approvalId) {
            approvalId
            outreachId
            messageCommitment
            channel
            approvedBy
            issuedAt
            expiresAt
            status
          }
          executionReceipt(operationId: $operationId) {
            receiptId
            operationId
            eventId
            status
            reasonCode
            payload
            receiptHash
            createdAt
            completedAt
            proofStatus
          }
        }
        """,
        variable_values={
            "approvalId": "approval-02",
            "operationId": "operation-synthetic-01",
        },
        context_value={"db": db_session},
    )

    assert result.errors is None
    assert result.data["approval"] == {
        "approvalId": "approval-02",
        "outreachId": "outreach-02",
        "messageCommitment": VALID_COMMITMENT,
        "channel": "gmail",
        "approvedBy": "operator:synthetic",
        "issuedAt": "2026-07-23T06:00:00+00:00",
        "expiresAt": "2026-07-24T06:00:00+00:00",
        "status": "approved",
    }
    receipt = result.data["executionReceipt"]
    assert receipt == {
        "receiptId": "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
        "operationId": "operation-synthetic-01",
        "eventId": "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
        "status": "succeeded",
        "reasonCode": None,
        "payload": VALID_RECEIPT_PAYLOAD,
        "receiptHash": VALID_RECEIPT_HASH,
        "createdAt": "2026-07-23T06:00:00+00:00",
        "completedAt": "2026-07-23T06:01:00+00:00",
        "proofStatus": "server-recorded",
    }
    assert receipt["payload"]["signature"] == {
        "algorithm": "ed25519",
        "key_id": "pairwise:v1:KKKKKKKKKKKKKKKKKKKKKK",
        "signature": (
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
    }


@pytest.mark.asyncio
async def test_execution_receipt_rejects_row_completion_from_different_signed_minute(
    db_session,
):
    row = _receipt("operation-synthetic-01")
    db_session.add(row)
    db_session.commit()

    row.completed_at = NOW + timedelta(minutes=2)
    db_session.commit()

    result = await schema.execute(
        """
        query {
          executionReceipt(operationId: "operation-synthetic-01") {
            receiptId
            completedAt
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.data == {"executionReceipt": None}
    assert result.errors is not None
    assert (
        "completed_at does not match signed payload"
        in result.errors[0].message
    )


@pytest.mark.asyncio
async def test_governed_evidence_reads_return_null_for_unknown_exact_ids(db_session):
    result = await schema.execute(
        """
        query {
          approval(id: "approval-missing") { approvalId }
          executionReceipt(operationId: "operation-missing") { receiptId }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    assert result.data == {
        "approval": None,
        "executionReceipt": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        """
        query {
          outreachItem(id: "outreach-01") {
            outreachId
            freshness { sourceEventId }
          }
        }
        """,
        """
        query {
          outreach {
            items {
              outreachId
              freshness { sourceEventId }
            }
          }
        }
        """,
    ],
)
async def test_outreach_without_checkpoint_fails_closed(db_session, query):
    db_session.add(_outreach("outreach-01"))
    db_session.commit()

    result = await schema.execute(query, context_value={"db": db_session})

    assert result.errors
    assert "no projection checkpoint" in str(result.errors[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["opportunities", "applications", "relationships", "outreach"],
)
@pytest.mark.parametrize("first", [0, 101])
async def test_jobsearch_page_sizes_are_bounded(db_session, field, first):
    result = await schema.execute(
        f"query {{ {field}(first: {first}) {{ nextCursor }} }}",
        context_value={"db": db_session},
    )

    assert result.errors


def test_jobsearch_schema_has_no_mutation_root():
    assert schema.mutation is None


@pytest.mark.asyncio
async def test_authenticated_graphql_route_reads_jobsearch_projection(db_session):
    db_session.add_all(
        [
            _opportunity("opportunity-http", employer="HTTP Corp"),
            _checkpoint("opportunities"),
        ]
    )
    db_session.commit()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-api-key"},
        ) as client:
            response = await client.post(
                "/api/graphql",
                json={
                    "query": (
                        "query($id: String!) { "
                        "opportunity(id: $id) { opportunityId employer } "
                        "}"
                    ),
                    "variables": {"id": "opportunity-http"},
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "opportunity": {
                "opportunityId": "opportunity-http",
                "employer": "HTTP Corp",
            }
        }
    }


@pytest.mark.asyncio
async def test_read_only_graphql_route_reads_governed_evidence(
    db_session,
    monkeypatch,
):
    db_session.add_all(
        [
            _approval("approval-http", "outreach-http"),
            _receipt("operation-http"),
        ]
    )
    db_session.commit()
    monkeypatch.setenv("ULTRADEX_READ_TOKEN", "read-only-synthetic-token")
    monkeypatch.setenv("ULTRADEX_READ_ID", "reader:synthetic")

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer read-only-synthetic-token"},
        ) as client:
            response = await client.post(
                "/api/graphql",
                json={
                    "query": (
                        "query($approvalId: String!, $operationId: String!) { "
                        "approval(id: $approvalId) { approvalId outreachId } "
                        "executionReceipt(operationId: $operationId) { "
                        "receiptId operationId proofStatus } }"
                    ),
                    "variables": {
                        "approvalId": "approval-http",
                        "operationId": "operation-http",
                    },
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "approval": {
                "approvalId": "approval-http",
                "outreachId": "outreach-http",
            },
            "executionReceipt": {
                "receiptId": "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
                "operationId": "operation-http",
                "proofStatus": "server-recorded",
            },
        }
    }
