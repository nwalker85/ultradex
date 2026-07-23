from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from ravenhelm_contracts import JobSearchEventV1
from ravenhelm_contracts.accountability_v1 import ExecutionReceiptV1
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1

from core.jobsearch_commands import (
    JobSearchCommandRequest,
    JobSearchGatewayService,
)
from core.jobsearch_executors import (
    EvidenceIngestResult,
    JobSearchExecutor,
    OpportunityScoreResult,
    RelationshipSyncResult,
    RetryableCommandError,
)
from core.jobsearch_models import (
    ApplicationProjectionDB,
    JobSearchApprovalDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    OpportunityProjectionDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)
from core.models import OperationDB, OperationEventDB


NOW = datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)
COMMITMENT = f"sha256:{'a' * 64}"


class SourceAdapter:
    calls = 0

    async def ingest(self, command):
        self.calls += 1
        return EvidenceIngestResult(
            evidence_id="evidence-source-01",
            source_kind=command.parameters["source_kind"],
            source_ref=command.parameters["source_ref"],
            observed_at=command.parameters["observed_at"],
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
        )


class Scorer:
    calls = 0

    async def score(self, opportunity_id, lens):
        self.calls += 1
        return OpportunityScoreResult(
            score=91,
            explanation=f"Strong fit under {lens}.",
            risk_flags=("compensation-unverified",),
        )


class RelationshipResolver:
    calls = 0

    async def sync(self, opportunity_id, dex_contact_ref):
        self.calls += 1
        return RelationshipSyncResult(
            relationship_id="relationship-01",
            relevance_score=88,
            relevance_summary="Relevant former colleague.",
        )


class Sender:
    calls = 0

    async def send(
        self,
        *,
        outreach_id,
        channel,
        message_commitment,
        idempotency_key,
    ):
        self.calls += 1
        return "evidence-sent-01"


class RetrySource:
    def __init__(self):
        self.calls = 0

    async def ingest(self, command):
        self.calls += 1
        raise RetryableCommandError("source_timeout")


async def _accepted(
    db,
    publisher,
    issuer,
    command,
    parameters,
    key,
):
    await JobSearchGatewayService(publisher, issuer).submit_command(
        db,
        JobSearchCommandRequest(
            command=command,
            parameters=parameters,
            actor_id="operator:test",
            idempotency_key=key,
        ),
    )
    return publisher.commands[-1]


def _evidence(db):
    db.add(
        JobSearchEvidenceReferenceDB(
            evidence_id="evidence-01",
            source_kind="web",
            source_ref="web-source-01",
            classification="private",
            observed_at=NOW,
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
            created_at=NOW,
        )
    )
    db.commit()


def _opportunity(db, opportunity_id="opportunity-01"):
    row = OpportunityProjectionDB(
        id=opportunity_id,
        employer_name="Example",
        title="Platform Engineer",
        location=None,
        role_family=None,
        state="discovered",
        score=None,
        score_explanation=None,
        risk_flags=[],
        evidence_refs=[],
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(row)
    db.commit()
    return row


def _application(db):
    row = ApplicationProjectionDB(
        id="application-01",
        opportunity_id="opportunity-01",
        state="draft",
        stage_history=[
            {
                "status": "draft",
                "occurred_at": "2026-07-23T14:00:00Z",
            }
        ],
        artifact_refs=[],
        next_action=None,
        next_action_deadline=None,
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(row)
    db.commit()
    return row


def test_executor_registry_exactly_matches_shared_command_catalog(
    db_session,
    receipt_issuer,
):
    executor = JobSearchExecutor(db_session, receipt_issuer)
    assert frozenset(executor.command_names) == COMMAND_NAMES_V1


@pytest.mark.asyncio
async def test_sources_ingest_validates_and_persists_opaque_evidence(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    adapter = SourceAdapter()
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "sources.ingest",
        {
            "source_kind": "web",
            "source_ref": "web-source-01",
            "observed_at": "2026-07-23T14:00:00Z",
        },
        "ingest-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        source_adapter=adapter,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert adapter.calls == 1
    row = db_session.get(JobSearchEvidenceReferenceDB, "evidence-source-01")
    assert row.redacted_summary == "Public role metadata reviewed."
    assert "raw" not in str(row.__dict__).lower()


@pytest.mark.asyncio
async def test_opportunity_create_writes_projection_and_checkpoint_atomically(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    _evidence(db_session)
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "opportunities.create",
        {
            "employer": "Example",
            "title": "Platform Engineer",
            "source_evidence_id": "evidence-01",
        },
        "create-01",
    )

    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
    ).execute(command)

    row = db_session.get(
        OpportunityProjectionDB,
        outcome.result["opportunity_id"],
    )
    checkpoint = db_session.get(ProjectionCheckpointDB, "opportunities")
    assert row.state == "discovered"
    assert row.evidence_refs[0]["evidence_id"] == "evidence-01"
    assert row.source_event_id == outcome.event.control_surface_event.id
    assert checkpoint.source_event_id == row.source_event_id
    assert checkpoint.status == "fresh"
    assert (
        db_session.get(
            JobSearchExecutionReceiptDB,
            outcome.receipt.receipt_id,
        )
        is not None
    )


@pytest.mark.asyncio
async def test_score_transition_relationship_and_export_handlers(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    _opportunity(db_session)
    _application(db_session)
    scorer = Scorer()
    resolver = RelationshipResolver()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        scorer=scorer,
        relationship_resolver=resolver,
    )

    score = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "opportunities.score",
            {"opportunity_id": "opportunity-01", "lens": "executive"},
            "score-01",
        )
    )
    transition = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "applications.transition",
            {
                "application_id": "application-01",
                "status": "applied",
                "occurred_at": "2026-07-23T14:30:00Z",
            },
            "transition-01",
        )
    )
    relationship = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "relationships.sync",
            {
                "opportunity_id": "opportunity-01",
                "dex_contact_ref": "dex-contact-01",
            },
            "relationship-01",
        )
    )
    exported = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "evidence.export",
            {
                "subject_type": "opportunity",
                "subject_id": "opportunity-01",
                "profile": "accountability.v1",
            },
            "export-01",
        )
    )

    opportunity = db_session.get(OpportunityProjectionDB, "opportunity-01")
    application = db_session.get(ApplicationProjectionDB, "application-01")
    relation = db_session.get(RelationshipProjectionDB, "relationship-01")
    assert score.receipt.status == "succeeded"
    assert opportunity.score == 91
    assert opportunity.state == "qualified"
    assert transition.result["status"] == "applied"
    assert application.stage_history[-1]["status"] == "applied"
    assert relationship.result["relationship_id"] == relation.id
    assert relation.dex_contact_ref == "dex-contact-01"
    assert exported.result["evidence_ref"].startswith("evidence-")
    assert scorer.calls == resolver.calls == 1


@pytest.mark.asyncio
async def test_prepare_approve_and_send_requires_exact_live_approval(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    _opportunity(db_session)
    sender = Sender()
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        sender=sender,
        now=lambda: NOW,
    )
    prepared = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.prepare",
            {
                "opportunity_id": "opportunity-01",
                "channel": "gmail",
                "message_commitment": COMMITMENT,
            },
            "prepare-01",
        )
    )
    outreach_id = prepared.result["outreach_id"]
    approved = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.approve",
            {
                "outreach_id": outreach_id,
                "message_commitment": COMMITMENT,
            },
            "approve-01",
        )
    )
    approval_id = approved.result["approval_contract_id"]
    sent = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.send",
            {
                "outreach_id": outreach_id,
                "approval_contract_id": approval_id,
                "message_commitment": COMMITMENT,
                "channel": "gmail",
            },
            "send-01",
        )
    )

    row = db_session.get(OutreachProjectionDB, outreach_id)
    assert row.state == "sent"
    assert row.sent_evidence_ref == "evidence-sent-01"
    assert sent.receipt.status == "succeeded"
    assert sender.calls == 1

    replay = await executor.execute(
        fake_jobsearch_publisher.commands[-1]
    )
    assert replay.replayed is True
    assert sender.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("expired", "approval_expired"),
        ("commitment", "approval_commitment_mismatch"),
        ("channel", "approval_channel_mismatch"),
        ("outreach", "approval_outreach_mismatch"),
        ("rowref", "approval_contract_mismatch"),
        ("cancelled", "approval_inactive"),
    ],
)
async def test_send_refuses_invalid_approval_without_calling_sender(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
    mutation,
    expected_code,
):
    _opportunity(db_session)
    outreach = OutreachProjectionDB(
        id="outreach-01",
        opportunity_id="opportunity-01",
        relationship_id=None,
        state="approved",
        channel="gmail",
        message_commitment=COMMITMENT,
        approval_contract_ref=(
            "approval-other" if mutation == "rowref" else "approval-01"
        ),
        sent_evidence_ref=None,
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    approval = JobSearchApprovalDB(
        approval_id="approval-01",
        outreach_id=(
            "outreach-other" if mutation == "outreach" else "outreach-01"
        ),
        message_commitment=(
            f"sha256:{'b' * 64}" if mutation == "commitment" else COMMITMENT
        ),
        channel="linkedin" if mutation == "channel" else "gmail",
        approved_by="operator:test",
        issued_at=NOW - timedelta(hours=1),
        expires_at=(
            NOW - timedelta(minutes=1)
            if mutation == "expired"
            else NOW + timedelta(hours=1)
        ),
        status="cancelled" if mutation == "cancelled" else "approved",
    )
    db_session.add_all([outreach, approval])
    db_session.commit()
    sender = Sender()
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "outreach.send",
        {
            "outreach_id": "outreach-01",
            "approval_contract_id": "approval-01",
            "message_commitment": COMMITMENT,
            "channel": "gmail",
        },
        f"send-{mutation}",
    )

    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        sender=sender,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == expected_code
    assert sender.calls == 0
    event = JobSearchEventV1.from_dict(outcome.event.to_dict())
    assert event.control_surface_event.lifecycle_state == "refused"


@pytest.mark.asyncio
async def test_unbound_external_ports_refuse_without_io(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "sources.ingest",
        {
            "source_kind": "web",
            "source_ref": "web-source-01",
            "observed_at": "2026-07-23T14:00:00Z",
        },
        "unbound-source",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
    ).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "source_adapter_unbound"
    operation = db_session.get(OperationDB, command.context.operation_id)
    assert operation.status == "refused"


@pytest.mark.asyncio
async def test_retryable_failure_has_no_terminal_receipt_until_budget_exhausted(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    source = RetrySource()
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "sources.ingest",
        {
            "source_kind": "web",
            "source_ref": "web-source-01",
            "observed_at": "2026-07-23T14:00:00Z",
        },
        "retry-source",
    )
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        source_adapter=source,
        max_attempts=3,
    )

    with pytest.raises(RetryableCommandError):
        await executor.execute(command, attempt=1)
    with pytest.raises(RetryableCommandError):
        await executor.execute(command, attempt=2)
    assert (
        db_session.query(JobSearchExecutionReceiptDB)
        .filter_by(operation_id=command.context.operation_id)
        .count()
        == 0
    )

    terminal = await executor.execute(command, attempt=3)
    assert terminal.receipt.status == "failed"
    assert source.calls == 3
    assert (
        db_session.query(JobSearchExecutionReceiptDB)
        .filter_by(operation_id=command.context.operation_id)
        .count()
        == 1
    )
    retry_events = [
        row.event_type
        for row in db_session.query(OperationEventDB)
        .filter_by(operation_id=command.context.operation_id)
        .order_by(OperationEventDB.id)
    ]
    assert retry_events.count("task.retrying") == 2
