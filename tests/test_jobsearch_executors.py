from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from ravenhelm_contracts import JobSearchEventV1
from ravenhelm_contracts.accountability_v1 import ExecutionReceiptV1
from ravenhelm_contracts.jobsearch_v1 import COMMAND_NAMES_V1
from sqlalchemy.orm import Session

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
    LeadDB,
    OpportunityProjectionDB,
    OrganizationDB,
    OutreachProjectionDB,
    ProjectionCheckpointDB,
    RelationshipProjectionDB,
)
from core.jobsearch_projections import (
    get_lead,
    get_organization,
    list_leads,
    list_organizations,
)
from core.jobsearch_receipts import verify_receipt_signature
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
            relationship_id=f"relationship-0{self.calls}",
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


class TransactionObserverSource:
    def __init__(self, bind):
        self._bind = bind
        self.visible_operation_status = None

    async def ingest(self, command):
        with Session(bind=self._bind) as observer:
            self.visible_operation_status = observer.get(
                OperationDB,
                command.context.operation_id,
            ).status
        return EvidenceIngestResult(
            evidence_id="evidence-observer-01",
            source_kind=command.parameters["source_kind"],
            source_ref=command.parameters["source_ref"],
            observed_at=command.parameters["observed_at"],
            commitment=COMMITMENT,
            redacted_summary="Public role metadata reviewed.",
        )


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


async def _prepared_outreach(
    db,
    publisher,
    issuer,
    executor,
    *,
    idempotency_key,
):
    prepared = await executor.execute(
        await _accepted(
            db,
            publisher,
            issuer,
            "outreach.prepare",
            {
                "opportunity_id": "opportunity-01",
                "channel": "gmail",
                "message_commitment": COMMITMENT,
            },
            idempotency_key,
        )
    )
    return prepared.result["outreach_id"]


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
async def test_sources_ingest_same_evidence_id_is_idempotent(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    adapter = SourceAdapter()
    first = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "sources.ingest",
        {
            "source_kind": "web",
            "source_ref": "web-source-01",
            "observed_at": "2026-07-23T14:00:00Z",
        },
        "ingest-idem-1",
    )
    second = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "sources.ingest",
        {
            "source_kind": "web",
            "source_ref": "web-source-01",
            "observed_at": "2026-07-23T15:00:00Z",
        },
        "ingest-idem-2",
    )
    executor = JobSearchExecutor(
        db_session,
        receipt_issuer,
        source_adapter=adapter,
    )
    first_outcome = await executor.execute(first)
    second_outcome = await executor.execute(second)
    assert first_outcome.receipt.status == "succeeded"
    assert second_outcome.receipt.status == "succeeded"
    assert adapter.calls == 2
    rows = db_session.query(JobSearchEvidenceReferenceDB).filter_by(
        evidence_id="evidence-source-01",
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_executor_does_not_release_operation_transaction_before_side_effect(
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
        "transaction-observer",
    )
    source = TransactionObserverSource(db_session.get_bind())

    await JobSearchExecutor(
        db_session,
        receipt_issuer,
        source_adapter=source,
    ).execute(command)

    assert source.visible_operation_status == "pending"


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


@pytest.mark.asyncio
async def test_workspace_initialize_succeeds_without_a_projection(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "workspace.initialize",
        {},
        "workspace-init-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result == {
        "workspace_id": "workspace-private",
        "status": "initialized",
    }


@pytest.mark.asyncio
async def test_applications_create_originates_draft_row_and_stays_transitionable(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    """BE-6: applications.create is the only way an Application row ever
    originates. Prove the row exists at the FSM's initial `draft` state and
    that the pre-existing applications.transition executor still operates on
    a row born from this new command (not just on fixture-seeded rows)."""
    _opportunity(db_session)
    executor = JobSearchExecutor(db_session, receipt_issuer)

    created = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "applications.create",
            {
                "opportunity_id": "opportunity-01",
                "occurred_at": "2026-07-23T14:15:00Z",
            },
            "application-create-01",
        )
    )

    application_id = created.result["application_id"]
    row = db_session.get(ApplicationProjectionDB, application_id)
    assert created.receipt.status == "succeeded"
    assert created.result["status"] == "draft"
    assert row is not None
    assert row.state == "draft"
    assert row.opportunity_id == "opportunity-01"
    assert row.stage_history == [
        {"status": "draft", "occurred_at": "2026-07-23T14:15:00Z"}
    ]
    assert row.source_event_id == created.event.control_surface_event.id

    transitioned = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "applications.transition",
            {
                "application_id": application_id,
                "status": "applied",
                "occurred_at": "2026-07-23T14:30:00Z",
            },
            "application-transition-after-create",
        )
    )

    db_session.refresh(row)
    assert transitioned.receipt.status == "succeeded"
    assert row.state == "applied"
    assert row.stage_history[-1]["status"] == "applied"


@pytest.mark.asyncio
async def test_applications_create_refuses_when_opportunity_is_missing(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "applications.create",
        {
            "opportunity_id": "opportunity-missing",
            "occurred_at": "2026-07-23T14:15:00Z",
        },
        "application-create-missing-opportunity",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "opportunity_not_found"
    assert db_session.query(ApplicationProjectionDB).count() == 0


@pytest.mark.asyncio
async def test_outreach_cancel_from_pending_approval_reaches_terminal_cancelled(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    _opportunity(db_session)
    executor = JobSearchExecutor(db_session, receipt_issuer, now=lambda: NOW)
    outreach_id = await _prepared_outreach(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        executor,
        idempotency_key="prepare-cancel-pending",
    )

    cancelled = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.cancel",
            {
                "outreach_id": outreach_id,
                "reason": "Role closed by employer.",
            },
            "cancel-pending-01",
        )
    )

    row = db_session.get(OutreachProjectionDB, outreach_id)
    assert cancelled.receipt.status == "succeeded"
    assert cancelled.result["status"] == "cancelled"
    assert cancelled.result["reason"] == "Role closed by employer."
    assert row.state == "cancelled"


@pytest.mark.asyncio
async def test_outreach_cancel_kills_the_expired_approval_dead_end(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    """BE-7: an outreach approved but never sent before its approval window
    lapses used to be stuck in `approved` forever — outreach.send correctly
    refuses `approval_expired`, and no other legal transition existed.
    outreach.cancel must accept an `approved` record even after its linked
    approval has expired, because cancellation only inspects outreach.state,
    never approval liveness. This is the documented outreach dead end."""
    _opportunity(db_session)
    executor = JobSearchExecutor(db_session, receipt_issuer, now=lambda: NOW)
    outreach_id = await _prepared_outreach(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        executor,
        idempotency_key="prepare-cancel-expired",
    )
    approved = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.approve",
            {"outreach_id": outreach_id, "message_commitment": COMMITMENT},
            "approve-cancel-expired",
        )
    )
    approval_id = approved.result["approval_contract_id"]
    approval = db_session.get(JobSearchApprovalDB, approval_id)
    approval.expires_at = NOW - timedelta(hours=1)
    db_session.commit()

    send_attempt = await executor.execute(
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
            "send-blocked-by-expiry",
        )
    )
    assert send_attempt.result["reason_code"] == "approval_expired"

    cancelled = await executor.execute(
        await _accepted(
            db_session,
            fake_jobsearch_publisher,
            receipt_issuer,
            "outreach.cancel",
            {
                "outreach_id": outreach_id,
                "reason": "Approval window lapsed; withdrawing outreach.",
            },
            "cancel-expired-01",
        )
    )

    row = db_session.get(OutreachProjectionDB, outreach_id)
    assert cancelled.receipt.status == "succeeded"
    assert cancelled.result["status"] == "cancelled"
    assert row.state == "cancelled"
    assert row.approval_contract_ref == approval_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "illegal_state",
    ["draft", "sent", "cancelled", "failed"],
)
async def test_outreach_cancel_refuses_from_illegal_source_states(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
    illegal_state,
):
    _opportunity(db_session)
    outreach = OutreachProjectionDB(
        id="outreach-illegal",
        opportunity_id="opportunity-01",
        relationship_id=None,
        state=illegal_state,
        channel="gmail",
        message_commitment=COMMITMENT,
        approval_contract_ref=None,
        sent_evidence_ref=None,
        source_event_id="event-seed",
        source_event_position="JOBSEARCH:seed",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(outreach)
    db_session.commit()
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "outreach.cancel",
        {
            "outreach_id": "outreach-illegal",
            "reason": "Testing illegal transition.",
        },
        f"cancel-illegal-{illegal_state}",
    )

    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "invalid_outreach_cancel_transition"
    row = db_session.get(OutreachProjectionDB, "outreach-illegal")
    assert row.state == illegal_state


@pytest.mark.asyncio
async def test_outreach_cancel_refuses_when_outreach_is_missing(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "outreach.cancel",
        {"outreach_id": "outreach-missing", "reason": "Never existed."},
        "cancel-missing-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "outreach_not_found"


@pytest.mark.asyncio
async def test_leads_create_persists_unapplied_lead(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.create",
        {
            "employer": "Anthropic",
            "title": "Systems Architect",
            "source_board": "linkedin",
            "external_id": "req-12345",
            "location": "San Francisco, CA",
            "remote_type": "hybrid",
            "salary_min": 250000,
            "salary_max": 350000,
            "fit_score": 92,
            "match_breakdown": {"skills_fit": 95, "domain_fit": 90},
            "risk_flags": ["compensation-unverified"],
            "requirements": ["Distributed Systems", "Python", "Kubernetes"],
        },
        "lead-create-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["employer"] == "Anthropic"
    assert outcome.result["title"] == "Systems Architect"
    assert outcome.result["status"] == "unapplied"
    assert outcome.result["fit_score"] == 92

    lead_id = outcome.result["lead_id"]
    row = db_session.get(LeadDB, lead_id)
    assert row is not None
    assert row.employer == "Anthropic"
    assert row.title == "Systems Architect"
    assert row.source_board == "linkedin"
    assert row.state == "unapplied"
    assert row.fit_score == 92.0
    assert row.requirements == ["Distributed Systems", "Python", "Kubernetes"]
    assert row.risk_flags == ["compensation-unverified"]
    assert row.converted_opportunity_id is None

    checkpoint = db_session.get(ProjectionCheckpointDB, "leads")
    assert checkpoint is not None
    assert checkpoint.status == "fresh"


@pytest.mark.asyncio
async def test_leads_create_validates_fit_score_bounds(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.create",
        {
            "employer": "OpenAI",
            "title": "Research Engineer",
            "fit_score": 150,
        },
        "lead-invalid-score-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)
    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "invalid_lead_parameters"


@pytest.mark.asyncio
async def test_leads_convert_atomic_pipeline_creation(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    lead = LeadDB(
        id="lead-convert-01",
        source_board="anthropic",
        external_id="ats-999",
        employer="Anthropic",
        organization_id=None,
        title="Principal AI Infrastructure Architect",
        location="Remote",
        remote_type="remote",
        salary_min=280000,
        salary_max=380000,
        salary_currency="USD",
        url="https://anthropic.com/careers/999",
        description="Lead AI infrastructure architecture",
        requirements=["Kubernetes", "PyTorch", "Rust"],
        fit_score=94.0,
        match_breakdown={"production_ml": "Expert", "systems": "Expert"},
        risk_flags=[],
        state="unapplied",
        converted_opportunity_id=None,
        source_event_id="pending",
        source_event_position="pending",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(lead)
    db_session.commit()

    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {
            "lead_id": "lead-convert-01",
            "stage": "applied",
            "target_role_family": "engineering_leadership",
            "next_action": "Follow up with recruiter after 5 days",
        },
        "lead-convert-key-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["status"] == "converted"
    opp_id = outcome.result["opportunity_id"]
    app_id = outcome.result["application_id"]

    # 1. Lead state
    lead_row = db_session.get(LeadDB, "lead-convert-01")
    assert lead_row.state == "converted"
    assert lead_row.converted_opportunity_id == opp_id

    # 2. Opportunity state
    opp_row = db_session.get(OpportunityProjectionDB, opp_id)
    assert opp_row is not None
    assert opp_row.employer_name == "Anthropic"
    assert opp_row.title == "Principal AI Infrastructure Architect"
    assert opp_row.state == "qualified"
    assert opp_row.score == 94.0
    assert len(opp_row.evidence_refs) == 1
    assert opp_row.evidence_refs[0]["evidence_id"] == "evidence-lead-lead-convert-01"

    # 3. Application state
    app_row = db_session.get(ApplicationProjectionDB, app_id)
    assert app_row is not None
    assert app_row.opportunity_id == opp_id
    assert app_row.state == "applied"
    assert app_row.next_action == "Follow up with recruiter after 5 days"
    assert len(app_row.stage_history) == 1
    assert app_row.stage_history[0]["status"] == "applied"


@pytest.mark.asyncio
async def test_leads_convert_with_contact_relationships(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    lead = LeadDB(
        id="lead-rel-01",
        source_board="linkedin",
        employer="Deepgram",
        title="VP of Engineering",
        state="unapplied",
        fit_score=85.0,
        source_event_id="pending",
        source_event_position="pending",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(lead)
    db_session.commit()

    resolver = RelationshipResolver()
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {
            "lead_id": "lead-rel-01",
            "stage": "applied",
            "contact_refs": ["dex-contact-01", "dex-contact-02"],
        },
        "lead-convert-rel-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        relationship_resolver=resolver,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["relationships_synced"] == 2
    assert resolver.calls == 2

    opp_id = outcome.result["opportunity_id"]
    rels = db_session.query(RelationshipProjectionDB).filter_by(opportunity_id=opp_id).all()
    assert len(rels) == 2


@pytest.mark.asyncio
async def test_leads_convert_refuses_duplicate_conversion_fail_closed(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    lead = LeadDB(
        id="lead-already-conv",
        source_board="linkedin",
        employer="SoundHound",
        title="Director of Engineering",
        state="converted",
        converted_opportunity_id="opportunity-existing-01",
        source_event_id="pending",
        source_event_position="pending",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(lead)
    db_session.commit()

    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {"lead_id": "lead-already-conv"},
        "dup-convert-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "lead_already_converted"

    # Invariant: Lead remains unmodified and no new opportunity was created
    lead_row = db_session.get(LeadDB, "lead-already-conv")
    assert lead_row.converted_opportunity_id == "opportunity-existing-01"


@pytest.mark.asyncio
async def test_leads_convert_refuses_when_lead_not_found(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {"lead_id": "lead-nonexistent"},
        "missing-lead-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "lead_not_found"


@pytest.mark.asyncio
async def test_leads_convert_rolls_back_atomically_on_resolver_failure(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    lead = LeadDB(
        id="lead-fail-rollback",
        source_board="openai",
        employer="OpenAI",
        title="Member of Technical Staff",
        state="unapplied",
        source_event_id="pending",
        source_event_position="pending",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(lead)
    db_session.commit()

    class FailingResolver:
        async def sync(self, opp_id, dex_ref):
            raise RuntimeError("Database connection dropped during resolver sync")

    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {
            "lead_id": "lead-fail-rollback",
            "contact_refs": ["dex-contact-error"],
        },
        "lead-fail-key-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        relationship_resolver=FailingResolver(),
    ).execute(command)
    assert outcome.receipt.status == "failed"
    assert outcome.result["reason_code"] == "executor_failure"

    # Invariant: Atomic rollback ensures lead is untouched and zero orphan opportunities exist
    lead_row = db_session.get(LeadDB, "lead-fail-rollback")
    assert lead_row.state == "unapplied"
    assert lead_row.converted_opportunity_id is None
    opps = db_session.query(OpportunityProjectionDB).filter_by(employer_name="OpenAI").all()
    assert len(opps) == 0


@pytest.mark.asyncio
async def test_organizations_create_persists_record(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "organizations.create",
        {
            "name": "Anthropic",
            "domain": "anthropic.com",
            "industry": "Artificial Intelligence",
            "size": "500-1000",
            "advocacy_rating": 95,
            "notes": "Target employer - top alignment with sovereign AI.",
        },
        "org-create-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["name"] == "Anthropic"
    assert outcome.result["domain"] == "anthropic.com"
    org_id = outcome.result["organization_id"]
    assert org_id.startswith("organization-")

    org_row = db_session.get(OrganizationDB, org_id)
    assert org_row is not None
    assert org_row.name == "Anthropic"
    assert org_row.domain == "anthropic.com"
    assert org_row.advocacy_rating == 95.0

    checkpoint = db_session.get(ProjectionCheckpointDB, "organizations")
    assert checkpoint is not None
    assert checkpoint.status == "fresh"


@pytest.mark.asyncio
async def test_organizations_update_mutates_fields(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    org = OrganizationDB(
        id="organization-update-01",
        name="Parloa",
        domain="parloa.com",
        industry="Enterprise AI",
        size="200-500",
        advocacy_rating=75.0,
        notes="Initial review",
        source_event_id="pending",
        source_event_position="pending",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(org)
    db_session.commit()

    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "organizations.update",
        {
            "organization_id": "organization-update-01",
            "advocacy_rating": 88,
            "notes": "Spoke with Head of Talent - strong advocate found.",
        },
        "org-update-key-01",
    )
    outcome = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(command)

    assert outcome.receipt.status == "succeeded"
    assert outcome.result["status"] == "updated"

    org_row = db_session.get(OrganizationDB, "organization-update-01")
    assert org_row.advocacy_rating == 88.0
    assert org_row.notes == "Spoke with Head of Talent - strong advocate found."


@pytest.mark.asyncio
async def test_organizations_update_refuses_when_not_found(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "organizations.update",
        {
            "organization_id": "organization-nonexistent",
            "notes": "Updated note",
        },
        "org-missing-01",
    )
    outcome = await JobSearchExecutor(db_session, receipt_issuer).execute(command)

    assert outcome.receipt.status == "refused"
    assert outcome.result["reason_code"] == "organization_not_found"


@pytest.mark.asyncio
async def test_crm_commands_idempotency_replay(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    command = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "organizations.create",
        {
            "name": "Scale AI",
            "domain": "scale.com",
            "advocacy_rating": 82,
        },
        "idempotency-org-key",
    )
    executor = JobSearchExecutor(db_session, receipt_issuer, now=lambda: NOW)
    outcome1 = await executor.execute(command)
    assert outcome1.receipt.status == "succeeded"
    assert outcome1.replayed is False

    # Replay identical command
    outcome2 = await executor.execute(command)
    assert outcome2.receipt.status == "succeeded"
    assert outcome2.replayed is True
    assert outcome2.receipt.receipt_id == outcome1.receipt.receipt_id
    assert outcome2.result == outcome1.result


@pytest.mark.asyncio
async def test_cryptographic_receipt_signature_validation_across_crm_commands(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    # Succeeded outcome receipt verification
    cmd_lead = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.create",
        {"employer": "LivePerson", "title": "Staff Architect"},
        "sig-lead-01",
    )
    outcome_lead = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(cmd_lead)
    assert outcome_lead.receipt.status == "succeeded"
    verify_receipt_signature(outcome_lead.receipt, receipt_issuer.public_key_bytes)

    # Refused outcome receipt verification
    cmd_refused = await _accepted(
        db_session,
        fake_jobsearch_publisher,
        receipt_issuer,
        "leads.convert",
        {"lead_id": "lead-missing-sig-test"},
        "sig-lead-refused-01",
    )
    outcome_refused = await JobSearchExecutor(
        db_session,
        receipt_issuer,
        now=lambda: NOW,
    ).execute(cmd_refused)
    assert outcome_refused.receipt.status == "refused"
    verify_receipt_signature(outcome_refused.receipt, receipt_issuer.public_key_bytes)


def test_projections_leads_and_organizations_queries(db_session):
    # Seed an org and two leads
    org = OrganizationDB(
        id="organization-proj-01",
        name="Google",
        domain="google.com",
        source_event_id="event-1",
        source_event_position="JOBSEARCH:1",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    lead1 = LeadDB(
        id="lead-p-01",
        source_board="linkedin",
        employer="Google",
        title="Distinguished Engineer",
        fit_score=95.0,
        state="unapplied",
        source_event_id="event-1",
        source_event_position="JOBSEARCH:1",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    lead2 = LeadDB(
        id="lead-p-02",
        source_board="career_board",
        employer="Google",
        title="Director of Engineering",
        fit_score=78.0,
        state="unapplied",
        source_event_id="event-1",
        source_event_position="JOBSEARCH:1",
        projected_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add_all([org, lead1, lead2])
    db_session.commit()

    # Query organization
    found_org = get_organization(db_session, "organization-proj-01")
    assert found_org is not None
    assert found_org.name == "Google"

    org_page = list_organizations(db_session, first=10)
    assert len(org_page.items) >= 1

    # Query lead
    found_lead = get_lead(db_session, "lead-p-01")
    assert found_lead is not None
    assert found_lead.title == "Distinguished Engineer"

    # Filtered lead query
    high_fit_leads = list_leads(db_session, first=10, min_fit_score=90.0)
    assert len(high_fit_leads.items) == 1
    assert high_fit_leads.items[0].id == "lead-p-01"

