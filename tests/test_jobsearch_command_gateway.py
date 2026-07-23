from __future__ import annotations

import pytest
from ravenhelm_contracts import JobSearchCommandV1, JobSearchEventV1
from ravenhelm_contracts.accountability_v1 import ExecutionReceiptV1

from core import DelegationService, OperationDB, OperationEventDB
from core.jobsearch_commands import (
    JobSearchCommandRequest,
    JobSearchDispatchError,
    JobSearchGatewayService,
)
from core.jobsearch_models import (
    JobSearchCommandDB,
    JobSearchExecutionReceiptDB,
    JobSearchLifecycleEventDB,
)
from tests.conftest import FakeJobSearchPublisher


PARAMETERS = {
    "employer": "Example",
    "title": "Platform Engineer",
    "source_evidence_id": "evidence-01",
}


@pytest.mark.asyncio
async def test_gateway_persists_and_publishes_one_canonical_command(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
    monkeypatch,
):
    monkeypatch.setenv("ULTRADEX_SERVICE_VERSION", "2.0.0")
    monkeypatch.setenv("ULTRADEX_DEPLOYMENT_SHA", "a" * 40)
    monkeypatch.setenv("ULTRADEX_ENVIRONMENT", "test")
    gateway = JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    )

    operation = await gateway.submit_command(
        db_session,
        JobSearchCommandRequest(
            command="opportunities.create",
            parameters=PARAMETERS,
            actor_id="operator:test",
            idempotency_key="create-01",
            correlation_id="correlation-01",
        ),
    )

    assert operation.status == "pending"
    assert len(fake_jobsearch_publisher.commands) == 1
    assert len(fake_jobsearch_publisher.events) == 1
    assert fake_jobsearch_publisher.events[0].domain_event_type.endswith(
        ".accepted.v1"
    )
    published = fake_jobsearch_publisher.commands[0]
    assert isinstance(published, JobSearchCommandV1)
    assert published.context.operation_id == operation.id
    assert published.context.contract_id == operation.id
    assert published.context.correlation_id == "correlation-01"
    assert published.context.actor_id == "operator:test"
    assert published.context.contract_version == "jobsearch.v1"
    assert published.context.schema_version == "control-surface.v1"
    assert published.parameters == PARAMETERS

    row = db_session.get(JobSearchCommandDB, operation.id)
    validated = JobSearchCommandV1.from_dict(
        {
            "command_id": row.command_id,
            "command": row.command_name,
            "actor_id": row.actor_id,
            "idempotency_key": row.idempotency_key,
            "context": row.context,
            "parameters": row.parameters,
        }
    )
    assert validated == published

    lifecycle = (
        db_session.query(JobSearchLifecycleEventDB)
        .filter_by(operation_id=operation.id)
        .one()
    )
    event = JobSearchEventV1.from_dict(lifecycle.payload)
    assert event.domain_event_type == "jobsearch.opportunities.create.accepted.v1"
    assert event.control_surface_event.lifecycle_state == "accepted"
    assert event.control_surface_event.metric_labels["result"] == "unknown"


@pytest.mark.asyncio
async def test_gateway_exact_replay_returns_one_operation_and_one_publish(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    gateway = JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    )
    request = JobSearchCommandRequest(
        command="opportunities.create",
        parameters=PARAMETERS,
        actor_id="operator:test",
        idempotency_key="create-01",
    )

    first = await gateway.submit_command(db_session, request)
    second = await gateway.submit_command(db_session, request)

    assert second.id == first.id
    assert db_session.query(OperationDB).count() == 1
    assert db_session.query(JobSearchCommandDB).count() == 1
    assert len(fake_jobsearch_publisher.commands) == 1


@pytest.mark.asyncio
async def test_gateway_conflicts_when_idempotency_envelope_changes(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    from core import IdempotencyConflictError

    gateway = JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    )
    await gateway.submit_command(
        db_session,
        JobSearchCommandRequest(
            command="opportunities.create",
            parameters=PARAMETERS,
            actor_id="operator:test",
            idempotency_key="create-01",
        ),
    )

    with pytest.raises(IdempotencyConflictError):
        await gateway.submit_command(
            db_session,
            JobSearchCommandRequest(
                command="opportunities.create",
                parameters={**PARAMETERS, "title": "Different"},
                actor_id="operator:test",
                idempotency_key="create-01",
            ),
        )

    assert db_session.query(OperationDB).count() == 1
    assert len(fake_jobsearch_publisher.commands) == 1


@pytest.mark.asyncio
async def test_gateway_rejects_unregistered_command_before_persistence(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    gateway = JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    )
    with pytest.raises(ValueError, match="command"):
        await gateway.submit_command(
            db_session,
            JobSearchCommandRequest(
                command="arbitrary.shell",
                parameters={},
                actor_id="operator:test",
                idempotency_key="bad-01",
            ),
        )

    assert db_session.query(OperationDB).count() == 0
    assert fake_jobsearch_publisher.commands == []


@pytest.mark.asyncio
async def test_gateway_binds_delegation_to_exact_command_and_id(
    db_session,
    fake_jobsearch_publisher,
    receipt_issuer,
):
    delegation = DelegationService.create_delegation(
        db_session,
        delegator="operator:test",
        delegatee="agent:research",
        allowed_actions=["opportunities.create"],
    )
    gateway = JobSearchGatewayService(
        fake_jobsearch_publisher,
        receipt_issuer,
    )

    accepted = await gateway.submit_command(
        db_session,
        JobSearchCommandRequest(
            command="opportunities.create",
            parameters=PARAMETERS,
            actor_id="agent:research",
            delegation_id=delegation.id,
            idempotency_key="delegated-01",
        ),
    )
    assert accepted.id

    with pytest.raises(PermissionError):
        await gateway.submit_command(
            db_session,
            JobSearchCommandRequest(
                command="opportunities.create",
                parameters=PARAMETERS,
                actor_id="agent:research",
                delegation_id="delegation:not-real",
                idempotency_key="delegated-02",
            ),
        )


@pytest.mark.asyncio
async def test_publish_failure_mints_failed_event_and_receipt(
    db_session,
    receipt_issuer,
):
    publisher = FakeJobSearchPublisher(fail_commands=True)
    gateway = JobSearchGatewayService(
        publisher,
        receipt_issuer,
    )

    with pytest.raises(JobSearchDispatchError) as raised:
        await gateway.submit_command(
            db_session,
            JobSearchCommandRequest(
                command="opportunities.create",
                parameters=PARAMETERS,
                actor_id="operator:test",
                idempotency_key="publish-failure",
            ),
        )

    operation = raised.value.operation
    assert operation.status == "failed"
    receipt_row = (
        db_session.query(JobSearchExecutionReceiptDB)
        .filter_by(operation_id=operation.id)
        .one()
    )
    receipt = ExecutionReceiptV1.from_dict(receipt_row.payload)
    assert receipt.status == "failed"
    assert receipt.reason_code == "executor_failure"
    lifecycle = (
        db_session.query(JobSearchLifecycleEventDB)
        .filter_by(operation_id=operation.id)
        .order_by(JobSearchLifecycleEventDB.occurred_at)
        .all()
    )
    assert len(lifecycle) == 2
    terminal = JobSearchEventV1.from_dict(lifecycle[-1].payload)
    assert terminal.control_surface_event.lifecycle_state == "failed"
    assert [event.control_surface_event.lifecycle_state for event in publisher.events] == [
        "accepted",
        "failed",
    ]
    assert all(row.published_at is not None for row in lifecycle)
    event_types = [
        row.event_type
        for row in db_session.query(OperationEventDB)
        .filter_by(operation_id=operation.id)
        .order_by(OperationEventDB.id)
    ]
    assert event_types == ["operation.accepted", "task.failed"]
