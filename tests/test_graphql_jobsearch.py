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


@pytest.mark.asyncio
async def test_candidate_profile_query(db_session):
    from core.jobsearch_profile import CandidateProfileStore
    CandidateProfileStore._cached_profile = None

    result = await schema.execute(
        """
        query {
          profile {
            candidateName
            title
            bio {
              fullName
              headline
              location
            }
            targetRoles
            targetDomains
            compensation {
              minBase
              targetTotal
              currency
            }
            skills {
              name
              category
              tier
              yearsExperience
            }
            expertSkills {
              name
              tier
            }
            advancedSkills {
              name
              tier
            }
            productionMl {
              llmOrchestration {
                name
                years
                coreTechnologies
              }
              llmSystems
              agenticOrchestration
            }
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    data = result.data["profile"]
    assert data["candidateName"] == "Nate Walker"
    assert "CTO" in data["title"]
    assert data["bio"]["fullName"] == "Nate Walker"
    assert len(data["targetRoles"]) >= 5
    assert data["compensation"]["minBase"] == 180000
    assert data["compensation"]["targetTotal"] == 250000
    assert len(data["skills"]) == 44
    assert len(data["expertSkills"]) == 22
    assert len(data["advancedSkills"]) == 22
    assert data["productionMl"]["llmOrchestration"]["name"] == "LLM Orchestration & Systems"


@pytest.mark.asyncio
async def test_leads_and_lead_detail_query(db_session):
    from core.jobsearch_models import LeadDB, OrganizationDB
    org = OrganizationDB(
        id="org-anthropic",
        name="Anthropic",
        domain="anthropic.com",
        industry="AI Research",
        size="500+",
        advocacy_rating=95.0,
    )
    lead1 = LeadDB(
        id="lead-01",
        source_board="Anthropic",
        external_id="ext-01",
        employer="Anthropic",
        organization_id="org-anthropic",
        title="Principal AI Architect",
        location="San Francisco, CA / Remote",
        remote_type="remote",
        salary_min=220000,
        salary_max=280000,
        salary_currency="USD",
        url="https://anthropic.com/careers/arch",
        description="Lead large-scale Claude model inference infrastructure.",
        requirements=["LLM", "Distributed Systems"],
        fit_score=94.5,
        match_breakdown={"skills": 95, "seniority": 94},
        risk_flags=[],
        state="discovered",
    )
    lead2 = LeadDB(
        id="lead-02",
        source_board="OpenAI",
        external_id="ext-02",
        employer="OpenAI",
        title="Member of Technical Staff",
        location="San Francisco, CA",
        remote_type="onsite",
        salary_min=200000,
        salary_max=260000,
        fit_score=75.0,
        match_breakdown={"skills": 75},
        risk_flags=["location-mismatch"],
        state="discovered",
    )
    db_session.add_all([org, lead1, lead2, _checkpoint("leads")])
    db_session.commit()

    result = await schema.execute(
        """
        query {
          leads(first: 5, minFitScore: 80.0) {
            items {
              id
              title
              employer
              fitScore
              matchBreakdown
              requirements
              riskFlags
              state
            }
            nextCursor
          }
          lead(id: "lead-01") {
            id
            title
            employer
            salaryMin
            salaryMax
            fitScore
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    page = result.data["leads"]
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == "lead-01"
    assert page["items"][0]["fitScore"] == 94.5
    assert page["items"][0]["requirements"] == ["LLM", "Distributed Systems"]

    single = result.data["lead"]
    assert single["id"] == "lead-01"
    assert single["title"] == "Principal AI Architect"
    assert single["salaryMin"] == 220000


@pytest.mark.asyncio
async def test_organizations_and_organization_detail_query(db_session):
    from core.jobsearch_models import OrganizationDB
    org1 = OrganizationDB(
        id="org-openai",
        name="OpenAI",
        domain="openai.com",
        industry="AI Research",
        size="1000+",
        advocacy_rating=90.0,
        notes="High engineering depth.",
    )
    org2 = OrganizationDB(
        id="org-deepgram",
        name="Deepgram",
        domain="deepgram.com",
        industry="Voice AI",
        size="200+",
        advocacy_rating=85.0,
        notes="Voice model pioneer.",
    )
    db_session.add_all([org1, org2, _checkpoint("organizations")])
    db_session.commit()

    result = await schema.execute(
        """
        query {
          organizations(first: 10, sortBy: "name") {
            items {
              id
              name
              domain
              industry
              advocacyRating
              notes
            }
          }
          organization(id: "org-openai") {
            id
            name
            advocacyRating
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    orgs = result.data["organizations"]["items"]
    names = [o["name"] for o in orgs]
    assert "Deepgram" in names
    assert "OpenAI" in names

    single = result.data["organization"]
    assert single["id"] == "org-openai"
    assert single["advocacyRating"] == 90.0


@pytest.mark.asyncio
async def test_contacts_and_contact_detail_query(db_session):
    from core.models import ContactDB
    contact = ContactDB(
        id="contact-01",
        name="Alice Recruiter",
        email="alice@techcorp.com",
        company="TechCorp",
        job_title="Lead Technical Recruiter",
        advocacy_score=92.0,
        relationship_tier="tier_1",
        communication_history=[
            {
                "id": "comm-01",
                "timestamp": "2026-08-20T10:00:00Z",
                "channel": "gmail",
                "direction": "inbound",
                "subject": "CTO Role Opportunity",
                "summary": "Inbound outreach regarding CTO role",
                "message_id": "msg-inbound-01",
            }
        ],
    )
    db_session.add(contact)
    db_session.commit()

    result = await schema.execute(
        """
        query {
          contacts(first: 5, search: "Alice") {
            items {
              id
              name
              email
              company
              advocacyScore
              relationshipTier
              communicationHistory {
                id
                channel
                direction
                subject
                summary
              }
            }
          }
          contact(id: "contact-01") {
            id
            name
            advocacyScore
            communicationHistory {
              id
              subject
            }
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    contacts = result.data["contacts"]["items"]
    assert len(contacts) == 1
    assert contacts[0]["name"] == "Alice Recruiter"
    assert contacts[0]["advocacyScore"] == 92.0
    assert len(contacts[0]["communicationHistory"]) == 1
    assert contacts[0]["communicationHistory"][0]["subject"] == "CTO Role Opportunity"

    single = result.data["contact"]
    assert single["id"] == "contact-01"
    assert single["name"] == "Alice Recruiter"


@pytest.mark.asyncio
async def test_next_best_actions_query(db_session):
    from core.jobsearch_models import ApplicationProjectionDB, LeadDB
    app_due = ApplicationProjectionDB(
        id="app-action-01",
        opportunity_id="opp-action-01",
        state="applied",
        next_action="Follow up with Hiring Manager",
        next_action_deadline=datetime.now(timezone.utc) - timedelta(days=1),
        source_event_id="evt-app-01",
        source_event_position="POS:1",
        projected_at=datetime.now(timezone.utc),
    )
    lead_high = LeadDB(
        id="lead-high-fit",
        source_board="Anthropic",
        employer="Anthropic",
        title="VP AI Engineering",
        fit_score=92.0,
        state="discovered",
    )
    db_session.add_all([app_due, lead_high, _checkpoint("applications")])
    db_session.commit()

    result = await schema.execute(
        """
        query {
          nextBestActions(limit: 5) {
            id
            urgency
            actionType
            title
            description
            entityType
            entityId
            score
            actionUrl
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    actions = result.data["nextBestActions"]
    assert len(actions) >= 1
    assert any(a["urgency"] in ["P0", "P1"] for a in actions)


@pytest.mark.asyncio
async def test_generate_recruiter_replies_query(db_session):
    result = await schema.execute(
        """
        query {
          generateRecruiterReplies(
            messageContext: {
              subject: "Exciting CTO Opportunity at AI Platform Co",
              bodyText: "Hi Nate, we have a Series B AI platform looking for a CTO with deep LLM systems and voice AI depth. Are you open to a chat?",
              senderEmail: "recruiter@aiplatform.co",
              senderName: "Sarah Connor",
              calendarSlots: [
                "Tuesday, Aug 26: 10:00 AM - 10:30 AM CT",
                "Wednesday, Aug 27: 02:00 PM - 02:30 PM CT"
              ]
            }
          ) {
            incomingMessageId
            senderName
            pills {
              pillType
              label
              subject
              bodyText
              calendarSlotsInjected
              requiresApproval
            }
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    replies = result.data["generateRecruiterReplies"]
    assert replies["senderName"] == "Sarah Connor"
    assert len(replies["pills"]) == 3
    pill_types = [p["pillType"] for p in replies["pills"]]
    assert "accept_and_schedule" in pill_types
    assert "request_scope_and_comp" in pill_types
    assert "polite_pass" in pill_types

    accept_pill = next(p for p in replies["pills"] if p["pillType"] == "accept_and_schedule")
    assert len(accept_pill["calendarSlotsInjected"]) == 2


@pytest.mark.asyncio
async def test_availability_and_calendar_events_query(db_session):
    result = await schema.execute(
        """
        query {
          availability(
            startDate: "2026-08-25",
            endDate: "2026-08-27",
            durationMinutes: 30
          ) {
            dateStr
            dayName
            slots30min {
              start
              end
              durationMinutes
              dayKey
              formattedCt
            }
          }
          calendarEvents {
            id
            summary
            isBusy
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    avail = result.data["availability"]
    assert len(avail) >= 1
    # Check that each day has 30min slots in Central Time
    for day in avail:
        assert len(day["slots30min"]) > 0
        assert "CT" in day["slots30min"][0]["formattedCt"]


@pytest.mark.asyncio
async def test_messages_query(db_session):
    from core.jobsearch_models import OutreachProjectionDB
    outreach = OutreachProjectionDB(
        id="msg-outreach-01",
        opportunity_id="opp-msg-01",
        relationship_id="contact-alice",
        state="approved",
        channel="gmail",
        message_commitment=VALID_COMMITMENT,
        approval_contract_ref="contract-msg-01",
        source_event_id="evt-msg-01",
        source_event_position="POS:1",
        projected_at=datetime.now(timezone.utc),
    )
    db_session.add(outreach)
    db_session.commit()

    result = await schema.execute(
        """
        query {
          messages(first: 10, channel: "gmail") {
            items {
              id
              channel
              direction
              subject
              status
              messageCommitment
            }
          }
        }
        """,
        context_value={"db": db_session},
    )

    assert result.errors is None
    msgs = result.data["messages"]["items"]
    assert len(msgs) == 1
    assert msgs[0]["id"] == "msg-outreach-01"
    assert msgs[0]["channel"] == "gmail"


@pytest.mark.asyncio
async def test_interview_debriefs_and_debrief_detail_query(db_session):
    from core.jobsearch_gjallarhorn import (
        InterviewDebriefExtractor,
        InterviewMetadata,
    )
    extractor = InterviewDebriefExtractor()
    meta = InterviewMetadata(
        company="SoundHound",
        role="VP of Conversational AI",
        round_type="System Design",
        interview_date="2026-08-24",
        interviewer_names=["Dr. Voice", "Lead Architect"],
        duration_minutes=45,
        opportunity_id="opp-soundhound-01",
    )
    transcript = (
        "[00:01] **Dr. Voice**: How do you architect sub-200ms voice streaming with ASR and TTS?\n"
        "[00:05] **Nate Walker**: We use WebSockets, streaming faster-whisper ASR on GPU, and chunked TTS synthesis.\n"
        "[00:10] **Lead Architect**: What about handling multi-agent orchestration latency?\n"
        "[00:15] **Nate Walker**: We enforce deterministic state machines with asynchronous tool calling via MCP.\n"
    )
    debrief = extractor.extract_debrief(transcript=transcript, metadata=meta)

    result = await schema.execute(
        """
        query($id: String!) {
          interviewDebriefs(first: 5, opportunityId: "opp-soundhound-01") {
            items {
              id
              metadata {
                company
                role
                roundType
              }
              executiveSummary
              questionsAndAnswers {
                question
                answerSummary
              }
              fitAssessment {
                overallScore
                recommendation
              }
              actionItems {
                title
                priority
              }
            }
          }
          interviewDebrief(id: $id) {
            id
            metadata {
              company
            }
            executiveSummary
          }
        }
        """,
        variable_values={"id": debrief.id},
        context_value={"db": db_session},
    )

    assert result.errors is None
    page = result.data["interviewDebriefs"]["items"]
    assert len(page) >= 1
    assert page[0]["metadata"]["company"] == "SoundHound"
    assert len(page[0]["questionsAndAnswers"]) >= 1

    single = result.data["interviewDebrief"]
    assert single["id"] == debrief.id
    assert single["metadata"]["company"] == "SoundHound"

