from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from core.jobsearch_models import (
    JOBSEARCH_COMMAND_TABLES,
    JobSearchApprovalDB,
    JobSearchCommandDB,
    JobSearchEvidenceReferenceDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
)
from core.models import OperationStatus


NOW = datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc)


def test_js_u03_table_catalog_is_exact():
    assert JOBSEARCH_COMMAND_TABLES == frozenset(
        {
            "jobsearch_commands",
            "jobsearch_evidence_refs",
            "jobsearch_approvals",
            "jobsearch_lifecycle_events",
            "jobsearch_execution_receipts",
        }
    )


def test_operation_status_includes_structured_refusal():
    assert OperationStatus.REFUSED.value == "refused"


def test_command_model_preserves_canonical_private_envelope(db_session):
    row = JobSearchCommandDB(
        operation_id="operation-01",
        command_id="command-01",
        command_name="opportunities.create",
        actor_id="operator:test",
        delegation_id=None,
        idempotency_key="create-01",
        context={"tenant_id": "private", "operation_id": "operation-01"},
        parameters={
            "employer": "Example",
            "title": "Platform Engineer",
            "source_evidence_id": "evidence-01",
        },
        created_at=NOW,
    )
    db_session.add(row)
    db_session.commit()

    stored = db_session.get(JobSearchCommandDB, "operation-01")
    assert stored is not None
    assert stored.command_id == "command-01"
    assert stored.parameters["source_evidence_id"] == "evidence-01"


def test_one_command_and_one_terminal_receipt_per_operation(db_session):
    db_session.add_all(
        [
            JobSearchCommandDB(
                operation_id="operation-01",
                command_id="command-01",
                command_name="evidence.export",
                actor_id="operator:test",
                idempotency_key="export-01",
                context={"operation_id": "operation-01"},
                parameters={
                    "subject_type": "opportunity",
                    "subject_id": "opportunity-01",
                    "profile": "accountability.v1",
                },
                created_at=NOW,
            ),
            JobSearchExecutionReceiptDB(
                receipt_id="receipt-01",
                operation_id="operation-01",
                event_id="event-01",
                status="succeeded",
                reason_code=None,
                payload={"receipt_id": "receipt-01"},
                receipt_hash=f"sha256:{'a' * 64}",
                created_at=NOW,
                completed_at=NOW,
            ),
        ]
    )
    db_session.commit()

    db_session.add(
        JobSearchExecutionReceiptDB(
            receipt_id="receipt-02",
            operation_id="operation-01",
            event_id="event-02",
            status="failed",
            reason_code="executor_failure",
            payload={"receipt_id": "receipt-02"},
            receipt_hash=f"sha256:{'b' * 64}",
            created_at=NOW,
            completed_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evidence_approval_and_lifecycle_rows_store_only_bounded_facts(db_session):
    evidence = JobSearchEvidenceReferenceDB(
        evidence_id="evidence-01",
        source_kind="web",
        source_ref="web-source-01",
        classification="private",
        observed_at=NOW,
        commitment=f"sha256:{'c' * 64}",
        redacted_summary="Public role metadata reviewed.",
        created_at=NOW,
    )
    approval = JobSearchApprovalDB(
        approval_id="approval-01",
        outreach_id="outreach-01",
        message_commitment=f"sha256:{'d' * 64}",
        channel="gmail",
        approved_by="operator:test",
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=24),
        status="approved",
    )
    event = JobSearchLifecycleEventDB(
        event_id="event-01",
        operation_id="operation-01",
        event_type="jobsearch.outreach.approved.v1",
        payload={"attributes": {"state": "approved"}},
        occurred_at=NOW,
        published_at=None,
    )
    db_session.add_all([evidence, approval, event])
    db_session.commit()

    assert db_session.get(JobSearchEvidenceReferenceDB, "evidence-01").classification == "private"
    assert db_session.get(JobSearchApprovalDB, "approval-01").expires_at is not None
    assert db_session.get(JobSearchLifecycleEventDB, "event-01").published_at is None
